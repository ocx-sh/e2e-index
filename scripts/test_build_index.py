"""Unit check for build_index.py's dry-run output: python3 scripts/test_build_index.py"""

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_index as b  # noqa: E402


class DryRun(unittest.TestCase):
    def test_layout_and_digests(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            catalog = b.build(out, {t: b.fixture_index(t) for t in b.TAGS}, "2026-01-01T00:00:00Z")
            self.assertEqual(set(catalog), {f"e2e/{r}" for r in ("claims", "oid", "tagged", "none", "future", "release")})
            for repository, digest in catalog.items():
                if repository == b.RELEASE_ROOT:
                    continue  # not generated; ReleaseRoot covers it
                root_bytes = (out / "p" / f"{repository}.json").read_bytes()
                self.assertEqual(b.sha256(root_bytes), digest)
                root = json.loads(root_bytes)
                self.assertEqual(root["repository"], "oci://ghcr.io/ocx-sh/e2e-package")
                self.assertEqual(set(root["tags"]), set(b.TAGS))
                self.assertEqual(root["name"], f"e2e.ocx.sh/{repository}")
                readme = (out / "p" / repository / "o" / "sha256" / f"{root['desc']['readme'].split(':')[1]}.md")
                self.assertEqual(b.sha256(readme.read_bytes()), root["desc"]["readme"])
                for row in root["tags"].values():
                    hex_digest = row["content"].split(":")[1]
                    obj = (out / "p" / repository / "o" / "sha256" / f"{hex_digest}.json").read_bytes()
                    self.assertEqual(b.sha256(obj), row["content"])
            self.assertEqual(json.loads((out / "c" / "index.json").read_text())["format_version"], 1)
            self.assertNotIn("publishers", json.loads((out / "p/e2e/none.json").read_text()))

    def test_publishers(self):
        values = b.publishers()
        claims = values["claims"][0]["claims"]
        self.assertEqual(claims["source_repository_identifier"], b.REPOSITORY_ID)
        self.assertEqual(
            set(values["oid"][0]["claims"]),
            {b.OID[k] for k in claims},
        )
        self.assertEqual(values["claims"][1]["kind"], "key")
        self.assertTrue(values["claims"][1]["key_pem"].startswith("-----BEGIN PUBLIC KEY-----"))
        self.assertIsNone(values["none"])
        self.assertEqual(values["future"][0], {"kind": "future"})
        self.assertIn("sigstore", values["future"][1])


class ReleaseRoot(unittest.TestCase):
    """`e2e/release` is written by announce and committed by hand; a rebuild must not drop or rewrite it."""

    def build(self, out):
        return b.build(out, {t: b.fixture_index(t) for t in b.TAGS}, "2026-01-01T00:00:00Z")

    def test_seeded_with_the_two_publishers_and_no_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            catalog = self.build(out)
            root_bytes = (out / "p/e2e/release.json").read_bytes()
            self.assertEqual(catalog["e2e/release"], b.sha256(root_bytes))
            root = json.loads(root_bytes)
            self.assertEqual(root["repository"], "oci://ghcr.io/ocx-sh/e2e-package")
            self.assertEqual(root["tags"], {})
            self.assertEqual(
                [p["claims"]["build_signer_uri"].split("workflows/")[1] for p in root["publishers"]],
                ["release.yml@refs/heads/main", "backfill.yml@refs/heads/main"],
            )
            for entry in root["publishers"]:
                self.assertEqual(entry["kind"], "keyless")
                self.assertEqual(entry["oidc_issuer"], b.ISSUER)
                self.assertEqual(entry["claims"]["source_repository_identifier"], b.REPOSITORY_ID)
                self.assertEqual(entry["claims"]["source_repository_owner_identifier"], b.OWNER_ID)

    def test_rebuild_keeps_a_root_announce_filled(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.build(out)
            path = out / "p/e2e/release.json"
            root = json.loads(path.read_text())
            root["tags"]["0.1.0"] = {"content": "sha256:" + "a" * 64, "observed": "2026-02-02T00:00:00Z"}
            committed = b.canonical(root)
            path.write_bytes(committed)
            catalog = self.build(out)
            self.assertEqual(path.read_bytes(), committed)
            self.assertEqual(catalog["e2e/release"], b.sha256(committed))
            on_disk = json.loads((out / "c/index.json").read_text())["packages"]
            self.assertEqual(on_disk["e2e/release"], b.sha256(committed))


class DefaultOut(unittest.TestCase):
    def test_wire_tree_lives_at_the_repository_root(self):
        # `ocx package announce` reads p/<pkg>.json and config.json from the repository root, as on ocx-sh/index.
        self.assertEqual(b.DEFAULT_OUT, Path(__file__).resolve().parent.parent)
        self.assertTrue((b.DEFAULT_OUT / "config.json").is_file())
        self.assertFalse((b.DEFAULT_OUT / "docs").exists())


class Variants(unittest.TestCase):
    """The six index copies the pages workflow signs (C-505): a full copy each, `tampered` carries a swapped root digest."""

    def make(self, tmp):
        src = Path(tmp) / "wire-src"
        b.build(src, {t: b.fixture_index(t) for t in b.TAGS}, "2026-01-01T00:00:00Z")
        out = Path(tmp) / "variants"
        b.make_variants(src, out)
        return src, out

    def test_six_full_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = self.make(tmp)
            self.assertEqual(sorted(p.name for p in out.iterdir()), sorted(b.VARIANTS))
            self.assertEqual(sorted(b.VARIANTS), ["expired", "key", "keyless", "tampered", "tampered-catalog", "unsigned"])
            for name in b.VARIANTS:
                self.assertTrue((out / name / "config.json").is_file(), name)
                self.assertEqual((out / name / "p/e2e/none.json").read_bytes(), (src / "p/e2e/none.json").read_bytes())
                if name != "tampered":
                    self.assertEqual((out / name / "c/index.json").read_bytes(), (src / "c/index.json").read_bytes(), name)

    def test_tampered_swaps_exactly_one_value_for_another_existing_root_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = self.make(tmp)
            good = json.loads((src / "c/index.json").read_text())["packages"]
            bad = json.loads((out / "tampered/c/index.json").read_text())["packages"]
            self.assertEqual(set(good), set(bad))
            changed = [k for k in good if good[k] != bad[k]]
            self.assertEqual(len(changed), 1)
            self.assertIn(bad[changed[0]], set(good.values()) - {good[changed[0]]})
            self.assertEqual(json.loads((out / "tampered/c/index.json").read_text())["format_version"], 1)


    def test_tampered_catalog_changes_bytes_only_after_signing_and_keeps_the_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = self.make(tmp)
            path = out / "tampered-catalog/c/index.json"
            signed = path.read_bytes()
            self.assertEqual(signed, (src / "c/index.json").read_bytes())
            b.alter_signed_catalog(out / "tampered-catalog")
            self.assertNotEqual(path.read_bytes(), signed)
            self.assertEqual(json.loads(path.read_bytes()), json.loads(signed))
            self.assertEqual((out / "keyless/c/index.json").read_bytes(), signed)

    def test_alter_signed_catalog_flag_runs_the_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self.make(tmp)
            before = (out / "tampered-catalog/c/index.json").read_bytes()
            subprocess.run([sys.executable, str(Path(b.__file__)), "--alter-signed-catalog", str(out / "tampered-catalog")], check=True)
            self.assertNotEqual((out / "tampered-catalog/c/index.json").read_bytes(), before)


# The same constant sits in ocx-sh/index bot-tools/tests/security/test_signing_job.py: both copies of the script must match.
SIGN_SCRIPT_SHA256 = "ee0d3f7eee9b440952bcd8e158187db61f4e6441736f718c67d85018b59a4252"


class SignCatalogScript(unittest.TestCase):
    """scripts/sign-catalog.sh with a stub `ocx`: `package exec` answers with the stub's own path, any other call is the signer."""

    SCRIPT = Path(__file__).resolve().parent / "sign-catalog.sh"
    PKG = "ghcr.io/ocx-sh/dev/cli@sha256:" + "a" * 64

    def run_script(self, args, pin=PKG, **env):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            stub, log, key = tmp / "ocx", tmp / "argv", tmp / "key"
            stub.write_text(
                "#!/bin/sh\n"
                f'if [ "$1" = package ]; then printf \'%s\\n\' "$@" > "{tmp / "resolve"}"; echo "$0"; exit 0; fi\n'
                f'printf \'%s\\n\' "$@" > "{log}"\n'
                f'printf \'%s\\n\' "${{OCX_SIGNING_KEY-unset}}" > "{key}"\n'
            )
            stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
            pin_file = tmp / "pin"
            pin_file.write_text(f"# comment\n{pin}\n")
            (tmp / "site" / "c").mkdir(parents=True)
            (tmp / "site" / "c" / "index.json").write_text("{}")
            full = {"PATH": f"{tmp}:{os.environ['PATH']}", "OCX_SIGN_PIN_FILE": str(pin_file), **env}
            result = subprocess.run([str(self.SCRIPT), str(tmp / "site"), *args], env=full, capture_output=True, text=True)
            read = lambda f: f.read_text().splitlines() if f.exists() else None
            return result, read(log), read(tmp / "resolve"), read(key), str(tmp / "site")

    def test_signs_with_the_defaults_and_passes_extra_args_through(self):
        result, argv, resolve, key, site = self.run_script(
            ["--key", "env://OCX_SIGNING_KEY"], SIGN_REGISTRY="e2e.ocx.sh", OCX_SIGNING_KEY="not-a-real-key"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(resolve[:4], ["package", "exec", self.PKG, "--"])
        self.assertEqual(
            argv,
            ["index", "sign", site, "--registry", "e2e.ocx.sh", "--expires-in-days", "30", "--key", "env://OCX_SIGNING_KEY"],
        )
        self.assertEqual(key, ["not-a-real-key"])

    def test_keyless_run_is_no_tty(self):
        _, argv, *_ = self.run_script([])
        self.assertEqual(argv[-1], "--no-tty")

    def test_expiry_days_are_overridable_and_zero_is_kept(self):
        _, argv, *_ = self.run_script([], SIGN_EXPIRES_DAYS="0")
        self.assertEqual(argv[argv.index("--expires-in-days") + 1], "0")

    def test_refuses_an_unusable_pin_before_running_ocx(self):
        for pin in ("ghcr.io/ocx-sh/dev/cli@sha256:" + "0" * 64, "ghcr.io/ocx-sh/dev/cli@sha256:PLACEHOLDER", ""):
            result, argv, resolve, *_ = self.run_script([], pin=pin)
            self.assertNotEqual(result.returncode, 0, pin)
            self.assertIsNone(argv)
            self.assertIsNone(resolve)

    def test_committed_pin_is_a_digest_pin(self):
        pin = [ln for ln in (self.SCRIPT.parent / "ocx-sign.pin").read_text().splitlines() if ln and not ln.startswith("#")]
        self.assertEqual(len(pin), 1)
        self.assertRegex(pin[0], r"^ghcr\.io/ocx-sh/dev/cli@sha256:[0-9a-f]{64}$")

    def test_script_is_the_copy_shared_with_ocx_sh_index(self):
        self.assertEqual(hashlib.sha256(self.SCRIPT.read_bytes()).hexdigest(), SIGN_SCRIPT_SHA256)


if __name__ == "__main__":
    unittest.main()

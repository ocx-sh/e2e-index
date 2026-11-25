"""Unit check for build_index.py's dry-run output: python3 scripts/test_build_index.py"""

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
    """The five index copies the pages workflow signs (C-505): a full copy each, `tampered` carries a swapped root digest."""

    def make(self, tmp):
        src = Path(tmp) / "wire-src"
        b.build(src, {t: b.fixture_index(t) for t in b.TAGS}, "2026-01-01T00:00:00Z")
        out = Path(tmp) / "variants"
        b.make_variants(src, out)
        return src, out

    def test_five_full_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = self.make(tmp)
            self.assertEqual(sorted(p.name for p in out.iterdir()), sorted(b.VARIANTS))
            self.assertEqual(sorted(b.VARIANTS), ["expired", "key", "keyless", "tampered", "unsigned"])
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


class SignCatalogScript(unittest.TestCase):
    """scripts/sign-catalog.sh with a stub `ocx` that records its argv."""

    SCRIPT = Path(__file__).resolve().parent / "sign-catalog.sh"

    def run_script(self, args, **env):
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "ocx"
            log = Path(tmp) / "argv"
            stub.write_text(f'#!/bin/sh\nprintf \'%s\\n\' "$@" > "{log}"\n')
            stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
            full = {"PATH": f"{tmp}:{os.environ['PATH']}", **env}
            result = subprocess.run([str(self.SCRIPT), *args], env=full, capture_output=True, text=True)
            return result, log.read_text().splitlines() if log.exists() else None

    PKG = "ghcr.io/ocx-sh/dev/cli@sha256:" + "a" * 64

    def test_signs_with_the_defaults_and_passes_extra_args_through(self):
        result, argv = self.run_script(["site", "--key", "env://OCX_SIGNING_KEY"], OCX_SIGN_PACKAGE=self.PKG, OCX_SIGN_REGISTRY="e2e.ocx.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            argv,
            ["package", "exec", self.PKG, "--", "ocx", "index", "sign", "site", "--registry", "e2e.ocx.sh",
             "--expires-in-days", "30", "--no-tty", "--key", "env://OCX_SIGNING_KEY"],
        )

    def test_expiry_days_are_overridable_and_zero_is_kept(self):
        _, argv = self.run_script(["site"], OCX_SIGN_PACKAGE=self.PKG, OCX_SIGN_EXPIRES_DAYS="0")
        self.assertEqual(argv[argv.index("--expires-in-days") + 1], "0")

    def test_refuses_a_placeholder_pin_before_running_ocx(self):
        result, argv = self.run_script(["site"], OCX_SIGN_PACKAGE="ghcr.io/ocx-sh/dev/cli@sha256:PLACEHOLDER")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PLACEHOLDER", result.stderr)
        self.assertIsNone(argv)

    def test_refuses_a_missing_pin(self):
        result, argv = self.run_script(["site"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(argv)


if __name__ == "__main__":
    unittest.main()

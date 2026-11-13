"""Unit check for build_index.py's dry-run output: python3 scripts/test_build_index.py"""

import json
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


if __name__ == "__main__":
    unittest.main()

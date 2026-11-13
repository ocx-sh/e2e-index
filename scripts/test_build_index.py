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
            self.assertEqual(set(catalog), {f"e2e/{r}" for r in ("claims", "oid", "tagged", "none", "future")})
            for repository, digest in catalog.items():
                root_bytes = (out / "p" / f"{repository}.json").read_bytes()
                self.assertEqual(b.sha256(root_bytes), digest)
                root = json.loads(root_bytes)
                self.assertEqual(root["repository"], "oci://ghcr.io/ocx-sh/e2e-package")
                self.assertEqual(set(root["tags"]), set(b.TAGS))
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


if __name__ == "__main__":
    unittest.main()

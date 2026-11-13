#!/usr/bin/env python3
"""Copy docs/ to .site-src/ with the root fields the catalog renderer requires but the wire roots omit.

The wire files under docs/ stay the served bytes (the workflow copies them over the rendered site afterwards);
this copy exists only so `ocx-catalog build` accepts the roots.
"""
import hashlib
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src, dst = root / "docs", root / ".site-src"
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(src, dst)
# What each root declares; shown as the catalog page's summary, above TESTING.md as its readme.
PUBLISHERS = {
    "claims": "keyless publisher matched by claim name, plus a key publisher",
    "oid": "the same claims keyed by raw OID, plus a key publisher",
    "tagged": "keyless publisher matching a tag-triggered release only",
    "none": "no publishers declared, so nothing is checked",
    "future": "only entries this ocx does not understand, so every install is refused",
}
readme = (root / "TESTING.md").read_bytes()
digest = hashlib.sha256(readme).hexdigest()
for path in sorted((dst / "p").glob("*/*.json")):
    doc = json.loads(path.read_text())
    desc = {
        "title": f"e2e/{path.stem}",
        "description": f"Fixture: {PUBLISHERS[path.stem]}.",
        "keywords": ["e2e", "publishers"],
        "readme": f"sha256:{digest}",
    }
    doc.update(name=f"e2e-index/{path.parent.name}/{path.stem}", desc=desc, status="active")
    path.write_text(json.dumps(doc))
    blob = path.with_suffix("") / "o" / "sha256" / f"{digest}.md"
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(readme)

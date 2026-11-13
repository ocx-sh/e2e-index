#!/usr/bin/env python3
"""Copy docs/ to .site-src/ with the root fields the catalog renderer requires but the wire roots omit.

The wire files under docs/ stay the served bytes (the workflow copies them over the rendered site afterwards);
this copy exists only so `ocx-catalog build` accepts the roots.
"""
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src, dst = root / "docs", root / ".site-src"
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(src, dst)
for path in sorted((dst / "p").glob("*/*.json")):
    doc = json.loads(path.read_text())
    doc.update(name=f"e2e-index/{path.parent.name}/{path.stem}", desc=None, status="active")
    path.write_text(json.dumps(doc))

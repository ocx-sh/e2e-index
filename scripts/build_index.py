#!/usr/bin/env python3
"""Generate the e2e.ocx.sh index site at the repository root from the tags published at ghcr.io/ocx-sh/e2e-package.

Layout and wire shapes follow the ocx index format: config.json, c/index.json, p/<repo>.json roots and
p/<repo>/o/sha256/<hex>.json dispatch objects (the OCI image index a tag resolves to, verbatim).

    build_index.py                 read every tag's image index from ghcr.io anonymously, write the repository root
    build_index.py --dry-run       fixture digests and a fixed timestamp, no network
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# The wire tree sits at the repository root, where `ocx package announce` reads it from the forge.
DEFAULT_OUT = Path(__file__).resolve().parent.parent
REGISTRY = "ghcr.io"
PACKAGE_PATH = "ocx-sh/e2e-package"
REPOSITORY = f"oci://{REGISTRY}/{PACKAGE_PATH}"
# The logical registry name clients configure; every root's `name` starts with it, as on ocx.sh.
INDEX_NAME = "e2e.ocx.sh"
# Each root's catalog page shows this file as its readme; rerun this script after editing it.
README = Path(__file__).resolve().parent.parent / "TESTING.md"
# One line per root for its catalog page; keys match publishers().
SUMMARY = {
    "claims": "keyless publisher matched by claim name, plus a key publisher",
    "oid": "the same claims keyed by raw OID, plus a key publisher",
    "tagged": "keyless publisher matching a tag-triggered release only",
    "none": "no publishers declared, so nothing is checked",
    "future": "only entries this ocx does not understand, so every install is refused",
}
# The one root this script does not generate: ocx's release pipeline announces into it (`announce --output`) and the
# entry is committed by hand. A rebuild seeds it when absent and otherwise leaves it, and its catalog line, alone.
RELEASE_ROOT = "e2e/release"
TAGS = ("main", "tag", "other", "key", "unsigned", "two-sboms")
INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"

# Values of `gh api repos/ocx-sh/e2e-package`: `id` and `owner.id`.
REPOSITORY_ID = "1455949009"
OWNER_ID = "263156444"
ISSUER = "https://token.actions.githubusercontent.com"
WORKFLOW_BASE = "https://github.com/ocx-sh/e2e-package/.github/workflows"
RELEASE_URI = f"{WORKFLOW_BASE}/release.yml@refs/heads/main"
BACKFILL_URI = f"{WORKFLOW_BASE}/backfill.yml@refs/heads/main"
TAG_IDENTITY_REGEXP = r"^https://github\.com/ocx-sh/e2e-package/\.github/workflows/release-tag\.yml@refs/tags/.+$"

# Fulcio extension OIDs by claim name; see C-006.
OID = {
    "source_repository_identifier": "1.3.6.1.4.1.57264.1.15",
    "source_repository_owner_identifier": "1.3.6.1.4.1.57264.1.17",
    "build_signer_uri": "1.3.6.1.4.1.57264.1.9",
    "build_trigger": "1.3.6.1.4.1.57264.1.20",
}

KEY_PEM_PATH = Path(__file__).resolve().parent.parent / "keys" / "e2e-key.pub"


def claims_entry(by_oid: bool) -> dict:
    claims = {
        "source_repository_identifier": REPOSITORY_ID,
        "source_repository_owner_identifier": OWNER_ID,
        "build_signer_uri": RELEASE_URI,
        "build_trigger": "workflow_dispatch",
    }
    if by_oid:
        claims = {OID[name]: value for name, value in claims.items()}
    return {"kind": "keyless", "oidc_issuer": ISSUER, "claims": claims}


def release_publishers() -> list[dict]:
    """The two identities of an own package: the release workflow and the backfill workflow, pinned to this repository."""
    return [
        {
            "kind": "keyless",
            "oidc_issuer": ISSUER,
            "claims": {
                "source_repository_identifier": REPOSITORY_ID,
                "source_repository_owner_identifier": OWNER_ID,
                "build_signer_uri": uri,
            },
        }
        for uri in (RELEASE_URI, BACKFILL_URI)
    ]


def publishers() -> dict[str, list | None]:
    """The `publishers` value of each root; None means the field is absent."""
    key = {"kind": "key", "key_pem": KEY_PEM_PATH.read_text()}
    return {
        "claims": [claims_entry(False), key],
        "oid": [claims_entry(True), key],
        "tagged": [{"kind": "keyless", "oidc_issuer": ISSUER, "identity_regexp": TAG_IDENTITY_REGEXP}],
        "none": None,
        "future": [
            {"kind": "future"},
            {
                "kind": "keyless",
                "oidc_issuer": ISSUER,
                "identity_regexp": TAG_IDENTITY_REGEXP,
                "sigstore": {"rekor_url": "https://rekor.sigstore.dev"},
            },
        ],
    }


def canonical(document: object) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def fixture_index(tag: str) -> bytes:
    platform = sha256(f"fixture-platform-manifest:{tag}".encode())
    return canonical(
        {
            "schemaVersion": 2,
            "mediaType": INDEX_MEDIA_TYPE,
            "manifests": [
                {
                    "digest": platform,
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "platform": {"architecture": "amd64", "os": "linux", "os.features": ["libc.glibc"]},
                    "size": 1,
                }
            ],
        }
    )


def fetch_index(tag: str) -> bytes:
    """The tag's OCI image index, byte for byte, read anonymously from the registry."""
    token_url = f"https://{REGISTRY}/token?" + urllib.parse.urlencode(
        {"service": REGISTRY, "scope": f"repository:{PACKAGE_PATH}:pull"}
    )
    with urllib.request.urlopen(token_url, timeout=30) as response:
        token = json.load(response)["token"]
    request = urllib.request.Request(
        f"https://{REGISTRY}/v2/{PACKAGE_PATH}/manifests/{tag}",
        headers={"Authorization": f"Bearer {token}", "Accept": INDEX_MEDIA_TYPE},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
    if json.loads(body).get("mediaType") != INDEX_MEDIA_TYPE:
        sys.exit(f"tag {tag} is not an OCI image index; the index records image indexes only")
    return body


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def build(out: Path, indexes: dict[str, bytes], observed: str) -> dict[str, str]:
    """Write the whole site; returns the catalog (`repository` -> root digest)."""
    write(out / "config.json", canonical({"format_version": 1}))
    readme = README.read_bytes()
    readme_digest = sha256(readme)
    catalog: dict[str, str] = {}
    for root_name, value in publishers().items():
        repository = f"e2e/{root_name}"
        tags = {}
        for tag, body in indexes.items():
            digest = sha256(body)
            write(out / "p" / repository / "o" / "sha256" / f"{digest.split(':')[1]}.json", body)
            tags[tag] = {"content": digest, "observed": observed}
        write(out / "p" / repository / "o" / "sha256" / f"{readme_digest.split(':')[1]}.md", readme)
        root: dict = {
            "name": f"{INDEX_NAME}/{repository}",
            "repository": REPOSITORY,
            "status": "active",
            "created": observed[:10],
            "desc": {
                "title": repository,
                "description": f"Fixture: {SUMMARY[root_name]}.",
                "keywords": ["e2e", "publishers"],
                "readme": readme_digest,
            },
            "tags": tags,
        }
        if value is not None:
            root["publishers"] = value
        root_bytes = canonical(root)
        write(out / "p" / f"{repository}.json", root_bytes)
        catalog[repository] = sha256(root_bytes)
    keep_release_root(out, observed, catalog)
    write(out / "c" / "index.json", canonical({"format_version": 1, "packages": catalog}))
    return catalog


def keep_release_root(out: Path, observed: str, catalog: dict[str, str]) -> None:
    """Seed `e2e/release` with no tags when absent, then record whatever root is on disk in the catalog."""
    path = out / "p" / f"{RELEASE_ROOT}.json"
    if not path.exists():
        readme = README.read_bytes()
        readme_digest = sha256(readme)
        write(out / "p" / RELEASE_ROOT / "o" / "sha256" / f"{readme_digest.split(':')[1]}.md", readme)
        root = {
            "name": f"{INDEX_NAME}/{RELEASE_ROOT}",
            "repository": REPOSITORY,
            "status": "active",
            "created": observed[:10],
            "desc": {
                "title": RELEASE_ROOT,
                "description": "Fixture: the package's own release pipeline, trusted by its two workflow identities.",
                "keywords": ["e2e", "release"],
                "readme": readme_digest,
            },
            "tags": {},
            "publishers": release_publishers(),
        }
        write(path, canonical(root))
    catalog[RELEASE_ROOT] = sha256(path.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true", help="use fixture digests; touch no network")
    args = parser.parse_args()
    if args.dry_run:
        indexes = {tag: fixture_index(tag) for tag in TAGS}
        observed = "2026-01-01T00:00:00Z"
    else:
        indexes = {tag: fetch_index(tag) for tag in TAGS}
        observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog = build(args.out, indexes, observed)
    print(json.dumps(catalog, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

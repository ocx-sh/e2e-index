# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The OCX Authors
"""``ocx package push --sign/--sbom`` writes no tag before every platform manifest it reaches is signed.

A push whose signing fails after the manifest landed must leave the destination's tag set unchanged:
no version tag, no cascade tag and no keep tag points at unsigned content from a run that reported red.
Key mode with an unset ``env://`` reference is the failure: it resolves at signing time, after the
platform manifest is already on the registry.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from src.helpers import make_package
from src.runner import OcxRunner
from tests.fixtures import attestations
from tests.test_push import push

pytestmark = pytest.mark.command("package_push")

UNSET_KEY = ["--key", "env://OCX_TEST_SIGNING_KEY_THAT_IS_NOT_SET"]


def registry_tags(registry: str, repo: str) -> set[str]:
    with urllib.request.urlopen(f"http://{registry}/v2/{repo}/tags/list", timeout=10) as response:
        return set(json.load(response).get("tags") or [])


@pytest.mark.parametrize("target", ["sign", "sbom"])
def test_a_push_whose_signing_fails_writes_no_tag(
    ocx: OcxRunner, unique_repo: str, tmp_path: Path, target: str
) -> None:
    pkg = make_package(ocx, unique_repo, "1.0.0", tmp_path)
    before = registry_tags(ocx.registry, pkg.repo)

    if target == "sign":
        flags = ["--sign"]
    else:
        sbom = tmp_path / "sbom.cdx.json"
        sbom.write_bytes(attestations.PRETTY_CYCLONEDX_PATH.read_bytes())
        flags = ["--sbom", str(sbom)]
    identifier = pkg.fq.rsplit(":", 1)[0] + ":2.0.0"
    result = push(ocx, pkg, tmp_path, ["--cascade", *flags, *UNSET_KEY], identifier=identifier)

    assert result.returncode != 0, f"a signing failure must fail the push: {result.stdout}"
    after = registry_tags(ocx.registry, pkg.repo)
    assert after == before, f"tags written by a push that failed to sign: {sorted(after - before)}"

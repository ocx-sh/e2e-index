"""`release_assets.py`'s proofs: the asset set equals v0.6.6's, and each archive keeps its layout."""

from __future__ import annotations

import json
import tarfile
import zipfile
from pathlib import Path

import pytest
import release_assets as ra

FIXTURES = Path(__file__).parent / "fixtures" / "v0.6.6"
CDX_JSON = {f"ocx-{a}.cdx.json" for a in ra.ASSET_TARGET.values()}


def fake_sbom(root: Path, fmt: str, target: str | None, stem: str) -> Path:
    out = root / ra.CDX_MANIFEST.parent / f"{stem}.cdx.{fmt}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"sbom {fmt} {target}", encoding="utf-8")
    return out


@pytest.fixture
def built(tmp_path: Path) -> Path:
    root, bins = tmp_path / "root", tmp_path / "bins"
    root.mkdir()
    for name in ra.EXTRA_FILES:
        (root / name).write_text(name, encoding="utf-8")
    for triple, asset in ra.ASSET_TARGET.items():
        exe = bins / triple / ("ocx.exe" if "windows" in asset else "ocx")
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"binary " + triple.encode())
    dist = tmp_path / "dist"
    ra.build(dist, "0.6.6", "a" * 40, bins, root, fake_sbom)
    return dist


def v066_names() -> set[str]:
    return set((FIXTURES / "assets.txt").read_text(encoding="utf-8").split())


def test_asset_names_equal_v066_plus_the_per_platform_sbom(built: Path) -> None:
    produced = {p.name for p in built.iterdir()}
    expected = v066_names()
    assert len(expected) == 19, "the v0.6.6 fixture stopped being read"
    assert produced - CDX_JSON == expected, (
        f"missing {expected - produced}, extra {produced - CDX_JSON - expected}"
    )
    assert CDX_JSON <= produced


def test_the_windows_alias_lives_in_one_map() -> None:
    windows = {t: a for t, a in ra.ASSET_TARGET.items() if "windows" in a}
    assert windows == {
        "x86_64-pc-windows-gnullvm": "x86_64-pc-windows-msvc",
        "aarch64-pc-windows-gnullvm": "aarch64-pc-windows-msvc",
    }


def test_the_unix_archive_layout_matches_v066(built: Path) -> None:
    listing = json.loads(
        (FIXTURES / "archive-listing.json").read_text(encoding="utf-8")
    )
    name = "ocx-x86_64-unknown-linux-gnu.tar.gz"
    with tarfile.open(built / name) as tar:
        assert sorted(tar.getnames()) == sorted(n.rstrip("/") for n in listing[name])
        assert tar.getmember("ocx-x86_64-unknown-linux-gnu/ocx").mode == 0o755


def test_the_windows_archive_layout_matches_v066(built: Path) -> None:
    listing = json.loads(
        (FIXTURES / "archive-listing.json").read_text(encoding="utf-8")
    )
    name = "ocx-x86_64-pc-windows-msvc.zip"
    with zipfile.ZipFile(built / name) as zf:
        assert sorted(zf.namelist()) == sorted(listing[name])


def test_checksums_follow_the_v066_format(built: Path) -> None:
    fixture = (FIXTURES / "sha256.sum").read_text(encoding="utf-8")
    ours = (built / "sha256.sum").read_text(encoding="utf-8")
    assert [line.split("*")[1] for line in ours.splitlines() if line] == [
        line.split("*")[1] for line in fixture.splitlines() if line
    ]
    assert ours.endswith("\n\n") and fixture.endswith("\n\n")
    per = (built / "ocx-x86_64-pc-windows-msvc.zip.sha256").read_text(encoding="utf-8")
    assert per.endswith(" *ocx-x86_64-pc-windows-msvc.zip\n\n")


def test_the_manifest_carries_the_v066_artifact_fields(built: Path) -> None:
    fixture = json.loads((FIXTURES / "dist-manifest.json").read_text(encoding="utf-8"))
    ours = json.loads((built / "dist-manifest.json").read_text(encoding="utf-8"))
    assert set(ours["artifacts"]) == set(fixture["artifacts"])
    for name, art in fixture["artifacts"].items():
        assert set(ours["artifacts"][name]) == set(art), name
        if "assets" in art:
            assert ours["artifacts"][name]["assets"] == art["assets"], name
    assert ours["releases"][0]["app_name"] == "ocx" and ours["releases"][0]["artifacts"]


def test_a_missing_binary_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ra.build(
            tmp_path / "d", "1.0.0", "a" * 40, tmp_path / "none", tmp_path, fake_sbom
        )

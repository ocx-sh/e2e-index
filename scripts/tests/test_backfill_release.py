"""`backfill_release.py`'s proofs, against a fake `ocx`: what it adds, what it skips, and what it refuses to guess."""

from __future__ import annotations

import json
from pathlib import Path

import backfill_release as bf
import pytest

IDENTITY = (
    "https://github.com/ocx-sh/ocx/.github/workflows/backfill.yml@refs/heads/main"
)
ISSUER = "https://token.actions.githubusercontent.com"
PACKAGE = "ghcr.io/ocx-sh/ocx/cli"


class FakeOcx:
    """A registry of `(ref, platform) -> {"sig", "sbom"}` held by IDENTITY; every call is recorded."""

    def __init__(
        self,
        platforms: dict[str, list[str]],
        held: dict[tuple[str, str], set[str]] | None = None,
    ) -> None:
        self.platforms = platforms
        self.held = held or {}
        self.calls: list[list[str]] = []
        self.verify_exit: int | None = None

    def __call__(self, argv: list[str]) -> tuple[int, str, str]:
        self.calls.append(argv)
        ref = argv[-1]
        if argv[:2] == ["--remote", "--format"]:
            listed = self.platforms.get(ref)
            if listed is None:
                return 79, "", "not found"
            return 0, json.dumps({"items": [{"package": ref, "platforms": listed}]}), ""
        verb = argv[1]
        platform = argv[argv.index("-p") + 1]
        key = (ref, platform)
        if verb == "verify":
            if self.verify_exit is not None:
                return self.verify_exit, "", "boom"
            kind = "sbom" if "--attestation" in argv else "sig"
            return (
                (0, "", "")
                if kind in self.held.get(key, set())
                else (79, "", "no signatures found")
            )
        kind = "sbom" if verb == "attest" else "sig"
        self.held.setdefault(key, set()).add(kind)
        return 0, "", ""

    def writes(self) -> list[str]:
        return [
            c[1]
            for c in self.calls
            if len(c) > 1 and c[0] == "package" and c[1] in {"sign", "attest"}
        ]


def tag_rows(fake: FakeOcx, dry_run: bool = False) -> list[bf.Row]:
    return bf.backfill_tag(
        fake,
        PACKAGE,
        "v0.6.6",
        IDENTITY,
        ISSUER,
        dry_run,
        lambda version, platform: Path("sbom.json"),
    )


def test_an_unsigned_platform_gets_its_signature_and_its_sbom() -> None:
    fake = FakeOcx({f"{PACKAGE}:0.6.6": ["linux/amd64", "darwin/arm64"]})
    rows = tag_rows(fake)
    assert [(r.platform, r.signature, r.sbom) for r in rows] == [
        ("darwin/arm64", "signed", "attested"),
        ("linux/amd64", "signed", "attested"),
    ]


def test_a_second_run_writes_nothing() -> None:
    fake = FakeOcx({f"{PACKAGE}:0.6.6": ["linux/amd64"]})
    tag_rows(fake)
    fake.calls.clear()
    rows = tag_rows(fake)
    assert fake.writes() == []
    assert [(r.signature, r.sbom) for r in rows] == [("skipped", "skipped")]


def test_each_half_is_judged_on_its_own() -> None:
    ref = f"{PACKAGE}:0.6.6"
    fake = FakeOcx({ref: ["linux/amd64"]}, {(ref, "linux/amd64"): {"sig"}})
    rows = tag_rows(fake)
    assert fake.writes() == ["attest"]
    assert (rows[0].signature, rows[0].sbom) == ("skipped", "attested")


def test_a_dry_run_reports_and_writes_nothing() -> None:
    fake = FakeOcx({f"{PACKAGE}:0.6.6": ["linux/amd64"]})
    rows = tag_rows(fake, dry_run=True)
    assert fake.writes() == []
    assert (rows[0].signature, rows[0].sbom) == ("would sign", "would attest")


def test_a_verify_failure_that_is_not_absence_never_licenses_a_signature() -> None:
    fake = FakeOcx({f"{PACKAGE}:0.6.6": ["linux/amd64"]})
    fake.verify_exit = 69
    with pytest.raises(bf.BackfillError, match="exited 69"):
        tag_rows(fake)
    assert fake.writes() == []


def test_a_version_with_no_package_is_reported_not_failed() -> None:
    rows = tag_rows(FakeOcx({}))
    assert [(r.platform, r.signature) for r in rows] == [("-", "no package")]


def test_main_refuses_a_ref_that_is_not_a_version_tag() -> None:
    assert (
        bf.main(
            ["--package", PACKAGE, "--identity", IDENTITY, "--issuer", ISSUER, "main"],
            run=FakeOcx({}),
        )
        == 64
    )


def test_main_exits_1_when_a_row_fails_and_still_prints_the_table(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeOcx({f"{PACKAGE}:0.6.6": ["linux/amd64"]})
    fake.verify_exit = 69
    code = bf.main(
        ["--package", PACKAGE, "--identity", IDENTITY, "--issuer", ISSUER, "v0.6.6"],
        run=fake,
    )
    assert code == 1
    assert "FAILED" in capsys.readouterr().out

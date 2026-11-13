"""`release_prune_select.py`'s proofs: what each mode selects, and what it must never touch."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import release_prune_select as sel

NOW = datetime(2026, 11, 13, 12, 0, 0, tzinfo=UTC)
TAGS = [
    "0.7.0-dev",
    "0.7.0-dev_20260101000000",
    "0.7.0-dev_20261112000000",
    "0.6.0",
    "0.6.0_20260901000000",
    "0.6.0-rc1",
    "0.6.0-rc1_20260820000000",
    "0.6.0-rc2_20260825000000",
    "0.7.0-rc1_20261110000000",
    "latest",
]


def test_dev_selects_only_old_build_tags_never_the_rolling_tag() -> None:
    assert sel.select_dev(TAGS, NOW - timedelta(days=30)) == [
        "0.7.0-dev_20260101000000"
    ]


def test_dev_with_zero_days_selects_every_build_and_still_not_the_rolling_tag() -> None:
    assert sel.select_dev(TAGS, NOW) == [
        "0.7.0-dev_20260101000000",
        "0.7.0-dev_20261112000000",
    ]


def test_candidates_need_their_final_release_to_be_old_enough() -> None:
    old = sel.select_candidates(TAGS, NOW - timedelta(days=30))
    assert old == ["0.6.0-rc1", "0.6.0-rc1_20260820000000", "0.6.0-rc2_20260825000000"]
    assert sel.select_candidates(TAGS, NOW - timedelta(days=90)) == []


def test_candidates_of_an_unreleased_version_are_never_selected() -> None:
    assert "0.7.0-rc1_20261110000000" not in sel.select_candidates(TAGS, NOW)


def test_candidates_never_include_the_stable_tags() -> None:
    assert {"0.6.0", "0.6.0_20260901000000", "latest"}.isdisjoint(
        sel.select_candidates(TAGS, NOW)
    )


def test_a_stamp_that_is_not_a_date_selects_nothing() -> None:
    assert sel.select_dev(["0.7.0-dev_20269999999999"], NOW) == []


def test_main_reads_stdin_and_rejects_negative_days(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("0.7.0-dev_20260101000000\n"))
    assert sel.main(["dev", "--days", "0", "--now", "2026-11-13T12:00:00+00:00"]) == 0
    assert capsys.readouterr().out.strip() == "0.7.0-dev_20260101000000"
    assert sel.main(["dev", "--days", "-1"]) == 64

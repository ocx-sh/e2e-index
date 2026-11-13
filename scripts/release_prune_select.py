#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The OCX Authors
"""Select the tags `release.yml` prunes, from a package's tag list on stdin.

    scripts/release_prune_select.py dev --days N [--now ISO] < tags
    scripts/release_prune_select.py candidates --days N [--now ISO] < tags

`dev` selects build tags `<X.Y.Z>-dev_<UTC>` whose build time is at least N days old; the rolling
`<X.Y.Z>-dev` tag is never selected. `candidates` selects every candidate tag of `<X.Y.Z>`
(`<X.Y.Z>-rc<N>_<UTC>` builds and rolling `<X.Y.Z>-rc<N>` tags) once the final `<X.Y.Z>_<UTC>` build is
at least N days old; before the final exists or while it is younger, nothing of that version is selected. One tag per line on
stdout. A tag that fits no shape is ignored, so a registry holding other tags selects nothing from them.

Exit codes: 0 selected (possibly nothing), 64 a bad argument.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

STAMP = "%Y%m%d%H%M%S"
DEV_BUILD = re.compile(r"^\d+\.\d+\.\d+-dev_(\d{14})$")
RELEASE_BUILD = re.compile(r"^(\d+\.\d+\.\d+)_(\d{14})$")
CANDIDATE = re.compile(r"^(\d+\.\d+\.\d+)(-rc[1-9]\d*)(?:_(\d{14}))?$")


def _built_at(stamp: str) -> datetime | None:
    try:
        return datetime.strptime(stamp, STAMP).replace(tzinfo=UTC)
    except ValueError:
        return None


def select_dev(tags: Iterable[str], cutoff: datetime) -> list[str]:
    chosen = []
    for tag in tags:
        match = DEV_BUILD.match(tag)
        built = _built_at(match.group(1)) if match else None
        if built is not None and built <= cutoff:
            chosen.append(tag)
    return sorted(chosen)


def select_candidates(tags: Iterable[str], cutoff: datetime) -> list[str]:
    tags = list(tags)
    final: set[str] = set()
    for tag in tags:
        match = RELEASE_BUILD.match(tag)
        built = _built_at(match.group(2)) if match else None
        if match and built is not None and built <= cutoff:
            final.add(match.group(1))
    # The final is the newest build of its line, so every candidate of that version goes together;
    # selecting the rolling tag with its builds avoids prune's shared-version refusal.
    chosen = []
    for tag in tags:
        match = CANDIDATE.match(tag)
        if match and match.group(1) in final:
            chosen.append(tag)
    return sorted(chosen)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("kind", choices=("dev", "candidates"))
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument(
        "--now", help="UTC time to measure from, ISO 8601; defaults to the clock"
    )
    args = parser.parse_args(argv)
    if args.days < 0:
        print("release_prune_select: --days must be >= 0", file=sys.stderr)
        return 64
    now = (
        datetime.fromisoformat(args.now).astimezone(UTC)
        if args.now
        else datetime.now(UTC)
    )
    cutoff = now - timedelta(days=args.days)
    tags = [line.strip() for line in sys.stdin if line.strip()]
    chosen = (
        select_dev(tags, cutoff)
        if args.kind == "dev"
        else select_candidates(tags, cutoff)
    )
    print("\n".join(chosen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

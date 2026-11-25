#!/usr/bin/env bash
# `indexbot check-expiry` for the ocx e2e suite, which passes `--url`; indexbot's flag is `--catalog`.
# Env: INDEXBOT (required) path of the indexbot executable.
set -euo pipefail

bin=${INDEXBOT:?INDEXBOT is unset: path of the indexbot executable}
args=()
for arg in "$@"; do
  [[ $arg == --url ]] && arg=--catalog
  args+=("$arg")
done
exec "$bin" check-expiry "${args[@]}"

#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# sign-catalog.sh -- sign the rendered index catalog in place.
#
# Usage: scripts/sign-catalog.sh DIR [extra `ocx index sign` flags...]
#
# Runs, with the ocx build pinned in scripts/ocx-sign.pin:
#   <that build's ocx> index sign DIR --registry ocx.sh \
#       --expires-in-days 30 [--no-tty unless --key] [extra flags]
# which rewrites DIR/c/index.json with `expires` and writes
# DIR/c/index.json.sigstore.json. Keyless with the ambient GitHub OIDC token
# unless the extra flags carry `--key`.
#
# Environment:
#   SIGN_REGISTRY       registry the index serves (default ocx.sh)
#   SIGN_EXPIRES_DAYS   catalog validity in days (default 30)
#   OCX_SIGN_PIN_FILE   pin file (default scripts/ocx-sign.pin)
#
# This file is shared byte for byte with ocx-sh/e2e-index; the pin lives in
# its own file so the two copies stay identical.

if [[ $# -lt 1 ]]; then
  echo "usage: sign-catalog.sh DIR [ocx index sign flags...]" >&2
  exit 2
fi
dir=$1
shift

[[ -f "$dir/c/index.json" ]] || { echo "sign-catalog.sh: $dir/c/index.json missing -- render first" >&2; exit 1; }

pin_file=${OCX_SIGN_PIN_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/ocx-sign.pin}
pin=$(grep -v -e '^[[:space:]]*#' -e '^[[:space:]]*$' "$pin_file" | head -n1 || true)
zeros=$(printf '0%.0s' {1..64})
if [[ ! "$pin" =~ ^ghcr\.io/ocx-sh/dev/cli@sha256:[0-9a-f]{64}$ || "$pin" == *"@sha256:$zeros" ]]; then
  echo "sign-catalog.sh: $pin_file holds no usable pin (got '${pin:-<empty>}'): set it to the digest of the ocx build that signs" >&2
  exit 1
fi

# Resolve the pinned build's executable and run it directly: `ocx package exec`
# strips credential-class OCX_* variables (OCX_SIGNING_KEY, OCX_KEY_PASSWORD) from its child.
signer=$(ocx package exec "$pin" -- sh -c 'command -v ocx')

# --no-tty is keyless-only: ocx rejects it next to --key.
no_tty=(--no-tty)
for arg in "$@"; do
  case $arg in --key | --key=*) no_tty=() ;; esac
done

exec "$signer" index sign "$dir" \
  --registry "${SIGN_REGISTRY:-ocx.sh}" \
  --expires-in-days "${SIGN_EXPIRES_DAYS:-30}" \
  ${no_tty[@]+"${no_tty[@]}"} "$@"

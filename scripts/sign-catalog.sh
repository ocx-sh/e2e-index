#!/usr/bin/env bash
# Sign the catalog of a rendered index tree with `ocx index sign`; the same bytes as ocx-sh/index scripts/sign-catalog.sh.
#
#   sign-catalog.sh DIR [ocx index sign args...]
#
# Env: OCX_SIGN_PACKAGE (required) the ocx package to run, pinned by digest;
#      OCX_SIGN_REGISTRY (default ocx.sh) the registry name written into the signed predicate;
#      OCX_SIGN_EXPIRES_DAYS (default 30). Keyless unless the extra args carry --key.
# Exit: 0 signed, 64 usage or placeholder pin, otherwise ocx's own code.
set -euo pipefail

dir=${1:?usage: sign-catalog.sh DIR [ocx index sign args...]}
shift
package=${OCX_SIGN_PACKAGE:?OCX_SIGN_PACKAGE is unset: pin the ocx package by digest}

case $package in
  *PLACEHOLDER*)
    echo "OCX_SIGN_PACKAGE is still a PLACEHOLDER: pin a ghcr.io/ocx-sh/dev/cli digest" >&2
    exit 64
    ;;
esac

exec ocx package exec "$package" -- ocx index sign "$dir" \
  --registry "${OCX_SIGN_REGISTRY:-ocx.sh}" \
  --expires-in-days "${OCX_SIGN_EXPIRES_DAYS:-30}" \
  --no-tty "$@"

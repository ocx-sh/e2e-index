# Testing the e2e fixtures by hand

Every command below was run against the live fixtures. They need an `ocx` built with publisher trust
([ocx-sh/ocx#696](https://github.com/ocx-sh/ocx/pull/696)): in an ocx checkout, `task run -- <args>` in place of
`ocx <args>`. ocx 0.6.6 and older ignore `publishers` and install every case.

## Setup

A throwaway home whose config points the logical registry `e2e.ocx.sh` at this index:

```sh
export OCX_HOME="$(mktemp -d)"
export OCX_CONFIG="$OCX_HOME/config.toml"
printf '[registries."e2e.ocx.sh"]\nindex = "https://ocx-sh.github.io/e2e-index"\n' >"$OCX_CONFIG"
```

## Install

```sh
ocx package install e2e.ocx.sh/e2e/<root>:<tag>
```

Every root points at the same repository, `ghcr.io/ocx-sh/e2e-package`; only the declared `publishers` differ.
The cell is the expected exit code.

| Tag (signed by) | `claims` | `oid` | `tagged` | `none` | `future` |
|---|---|---|---|---|---|
| `main` (`release.yml` on `refs/heads/main`) | 0 | 0 | 77 | 0 | 82 |
| `two-sboms` (the same workflow) | 0 | 0 | 77 | 0 | 82 |
| `key` (a key pair, no certificate) | 0 | 0 | 77 | 0 | 82 |
| `tag` (`release-tag.yml` on a tag ref) | 77 | 77 | 0 | 0 | 82 |
| `other` (`other-signer.yml`) | 77 | 77 | 77 | 0 | 82 |
| `unsigned` | 79 | 79 | 79 | 0 | 82 |

- 77 `publisher_mismatch`: signed, but by nobody the root lists.
- 79 `no_signatures_found`: the root lists publishers and the package has no signature.
- 82 `publishers_unrecognized`: the root lists only entries this ocx does not understand.
- `none` declares no publishers, so nothing is checked.

Add `--format json` before `package` to read the slug from `error.detail`.

## Settings and the opt-out

```sh
# skip the check: installs, with one warning
ocx package install --no-verify e2e.ocx.sh/e2e/claims:unsigned

# require publishers: a root that declares none is refused, exit 81 publishers_required
printf 'signatures = "required"\n' >>"$OCX_CONFIG"
OCX_HOME="$(mktemp -d)" ocx package install e2e.ocx.sh/e2e/none:unsigned
```

## SBOM and attestations

`package sbom` and `package verify` need `--platform`: without it they look at the image index, and only the
platform manifest is signed ([ocx-sh/ocx#694](https://github.com/ocx-sh/ocx/issues/694)), so they exit 79.

```sh
p='--platform linux/amd64+libc.glibc'

# lists two SBOMs, each verified against the declared publishers
ocx package sbom $p e2e.ocx.sh/e2e/claims:two-sboms

# writes the newer one: its metadata property e2e:sequence is "2"
ocx package sbom $p -o sbom.json e2e.ocx.sh/e2e/claims:two-sboms

# attestation signer is checked against publishers with no identity flags: 0, then 77
ocx package verify --attestation $p e2e.ocx.sh/e2e/claims:main
ocx package verify --attestation $p e2e.ocx.sh/e2e/claims:other
```

## Without the index

Straight at the registry there are no declared publishers, so the signer is named on the command line:

```sh
ocx package verify $p \
  --certificate-identity https://github.com/ocx-sh/e2e-package/.github/workflows/release.yml@refs/heads/main \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/ocx-sh/e2e-package:main

curl -fsSLO https://raw.githubusercontent.com/ocx-sh/e2e-index/main/keys/e2e-key.pub
ocx package verify $p --key e2e-key.pub ghcr.io/ocx-sh/e2e-package:key
```

The automated form of all this is `test/e2e/test_publisher_trust_public.py` in ocx-sh/ocx, run by this repository's
`client-e2e` workflow.

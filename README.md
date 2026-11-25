# e2e-index

End-to-end test fixture for the OCX index: the `publishers` an index root declares for a package. Not the real index.

It serves the logical registry `e2e.ocx.sh` as static files; every root points at `oci://ghcr.io/ocx-sh/e2e-package`
(see [`e2e-package`](https://github.com/ocx-sh/e2e-package)).

| Root | `publishers` |
|---|---|
| `e2e/claims` | keyless (GitHub issuer) with claims by name, plus the `key` entry |
| `e2e/oid` | the same claims keyed by raw OID, plus the `key` entry |
| `e2e/tagged` | keyless `identity_regexp` over `refs/tags/` |
| `e2e/none` | absent |
| `e2e/future` | one `{ "kind": "future" }` and one keyless entry carrying `sigstore` |

Every root lists the tags `main`, `tag`, `other`, `key`, `unsigned` and `two-sboms`.

## Generating the site

`scripts/build_index.py` reads each published tag's image index from ghcr.io anonymously and writes the wire tree at the repository root (`config.json`, `c/`, `p/`).
Run it only after the `e2e-package` tags are published. `--dry-run` writes fixture digests with no network access.
`python3 scripts/test_build_index.py` checks the dry-run output.

## Site

`.github/workflows/pages.yml` renders the root wire tree with the `ocx-catalog` renderer and publishes it through Pages.
The wire files keep their bytes and URLs; the index URL is `https://ocx-sh.github.io/e2e-index`.
Every root is named `e2e.ocx.sh/e2e/<root>`, so the site's copy buttons give refs a configured client resolves.

## Testing by hand

[TESTING.md](TESTING.md) has the setup, the expected exit code of every root and tag, and the SBOM and
attestation commands. Each package page of the site shows the same text.

## Signed variants

`pages.yml` also serves six full copies of the index, each signed by `scripts/sign-catalog.sh` (`ocx index sign`) on `main` only:

| Path | Signed with |
|---|---|
| `/keyless/` | this workflow's identity, 30 days |
| `/key/` | the key pair of the secrets `E2E_INDEX_SIGNING_KEY` and `E2E_INDEX_SIGNING_KEY_PASSWORD`; public half `keys/e2e-index-key.pub` (PEM, committed alongside the secrets) |
| `/expired/` | this workflow's identity, `--expires-in-days 0` |
| `/tampered/` | this workflow's identity, after one `packages` digest was swapped for another root's |
| `/tampered-catalog/` | this workflow's identity, after the catalog bytes were changed once signed, so the signature no longer matches |
| `/unsigned/` | not signed |

The signing binary is the digest-pinned `ghcr.io/ocx-sh/dev/cli` in `scripts/ocx-sign.pin`; `scripts/sign-catalog.sh` is the byte-identical copy of the one in ocx-sh/index. A weekly run keeps the 30-day expiry fresh.

## client-e2e

`.github/workflows/client-e2e.yml` runs on a push to `hex/signing-dogfood-index-signing` and on manual dispatch. It builds ocx from
`ocx_repository` (default `ocx-sh/ocx`) at `ocx_ref` (a 40-hex SHA or a branch, default the same branch) and runs `test/e2e` with
`-m e2e_public`, which includes the signed-variant cases and the expiry alert (`indexbot check-expiry`, installed from its branch).
The test run receives the built binary in `OCX_E2E_BINARY` and configures the `e2e.ocx.sh` index itself. It needs no secrets.

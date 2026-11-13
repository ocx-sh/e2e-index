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

`scripts/build_index.py` reads each published tag's image index from ghcr.io anonymously and writes `docs/`.
Run it only after the `e2e-package` tags are published. `--dry-run` writes fixture digests with no network access.
`python3 scripts/test_build_index.py` checks the dry-run output.

## GitHub Pages

Static site, no Jekyll (`docs/.nojekyll`). Pages source: branch `main`, folder `/docs`. The index URL is
`https://ocx-sh.github.io/e2e-index`.

## client-e2e

`.github/workflows/client-e2e.yml` (manual dispatch) builds ocx from `ocx_repository` (default `ocx-sh/ocx`) at a
40-hex `ocx_ref` and runs `test/e2e` with `-m e2e_public`. The test run receives the built binary in `OCX_E2E_BINARY`
and configures the `e2e.ocx.sh` index itself. It needs no secrets.

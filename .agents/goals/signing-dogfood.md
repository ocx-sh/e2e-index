# Goal: "Signing dogfood, loop A — ocx and ocx-mirror sign their own releases"

Source: .agents/discussions/signing-dogfood.md · Written: 2026-11-13 by /hex-loop

## Definition of done

- [ ] "GHCR dev channel" — evidence: the commit, PR comment or artifact that satisfies it. Scope: the release workflow's dev mode runs build, stamp, SBOM, sign and publish to `ghcr.io/ocx-sh/dev/cli` and nowhere else (unannounced, no git tag, no GitHub release); `deploy-dev.yml` no longer points at `dev.ocx.sh`; a repository selects such a build through an `ocx.toml` pin and `ocx.lock`.
- [ ] "Local publish task" — evidence: the commit, PR comment or artifact that satisfies it. Scope: one local task builds a stamped host binary and publishes it as a package to a local registry, other checkouts on the machine resolve it through an `OCX_MIRRORS` redirect, and it can optionally push to the GHCR dev namespace.
- [ ] "Bazel release replaces cargo-dist" — evidence: the commit, PR comment or artifact that satisfies it. Scope: a release workflow dispatched by hand from `refs/heads/main`, binaries from the hermetic Bazel cross builds (8 triples), a released binary reports its real commit, branch, timestamp and version; asset names, checksums, `dist-manifest.json` and what the installers download by name stay as they are.
- [ ] "Signed SBOM, signed manifest per platform" — evidence: the commit, PR comment or artifact that satisfies it. Scope: every platform's package carries its own CycloneDX SBOM as a signed attestation and a signed platform manifest, made in the run that pushed it; no tag is moved or announced before its signature exists.
- [ ] "Backfill, both proven in e2e" — evidence: the commit, PR comment or artifact that satisfies it. Scope: a second dispatched workflow behind a reviewer environment backfills signatures and SBOMs onto existing tags per platform and skips what its own identity already signed; the release and backfill workflows both run in `ocx-sh/e2e-package` on real tags with real GitHub-issued certificates.
- [ ] "Client carry-overs" — evidence: the commit, PR comment or artifact that satisfies it. Scope: `ocx package sbom` and `ocx package verify` select the host platform as `install` does; `--no-verify` and `OCX_NO_VERIFY` are refused under a system-locked `signatures = "required"` and no longer fail on an unreadable committed index root.
- [ ] "prune on GHCR via --forge" — evidence: the commit, PR comment or artifact that satisfies it. Scope: `ocx package prune` deletes on GHCR through the GitHub packages API, selected by `--forge` or inferred from the registry host.
- [ ] "ocx-mirror release cycle ported" — evidence: the commit, PR comment or artifact that satisfies it, including the `ocx-sh/ocx-mirror` PR URL. Scope: once the ocx side is green, the same workflow shape in `ocx-sh/ocx-mirror`: dispatched from `main`, release, candidate and dev modes, per-platform SBOM attestation and signature, backfill, dev builds to `ghcr.io/ocx-sh/dev/mirror`; no mirror feature work (SBOMs for mirrored packages, registry sync and re-signing stay in loop C); its release workflow uses the ocx this loop builds through an `ocx.toml` pin, and the swap to the released version is a recorded follow-up.
- [ ] "Release candidates" — evidence: the commit, PR comment or artifact that satisfies it. Scope: version `X.Y.Z-rc.N` as a dispatch input from `main`, announced `ephemeral`, GitHub release marked pre-release, no floating tag moved, never what the installer picks, pruned 30 days after the final release, proven as a full cycle in the fixtures only; `ocx install` plus `ocx select` on the ocx package switch a terminal to a candidate and back; the install script stays stable-only.
- [ ] "Registry docs measured" — evidence: the commit, PR comment or artifact that satisfies it. Scope: the registry table of `website/src/content/docs/publishing/snapshot-tracks.md` gains measured GHCR and gitlab.com rows, replacing the sentence that puts GHCR at exit 82 from documentation alone; the GitLab CI recipe keeps GitLab CI and a GitLab-hosted index, pushes packages to a registry that takes them, and the page says in one line that GitLab's registry is not a package host, linking https://github.com/ocx-sh/ocx/issues/480; `--forge gitlab` stays refused on `ocx package prune` and no GitLab fixture exists.
- [ ] PR merge-ready (DONE block only) — evidence: the PR URL, and the
  PR is not a draft.
- [ ] CI green per job (DONE block only) — evidence: every check run on
  the PR head SHA with its conclusion; every skipped job states its
  skip reason (its `if:` or path filter).
  A skip with no reason is not green.
- [ ] Deep verify passed (DONE block only) — evidence: the full documented verification result.

## Autonomy

- Prompting: never — no question waits for a human; a doubt runs
  § Issue resolution.
- Granted acts (authority: the pasted prompt): in ocx-sh/e2e-package and ocx-sh/e2e-index: "you are explicilty allowed to create, force push to, make tags, releases or change settings including gh secrets, same holds for other e2e repos"; one branch and one PR in ocx-sh/ocx-mirror: "pr for ocx-mirror is granted"; dispatch signed dev-channel runs of the release workflow in ocx-sh/ocx and ocx-sh/ocx-mirror, and push locally built pre-releases, publishing only to ghcr.io/ocx-sh/dev/*; never a production release, tag or backfill dispatch
- Forbidden or narrowed acts:
  - Never merge.
  - Never cut a production release, tag or backfill dispatch.
  - Never write to ocx.sh, ghcr.io/ocx-sh/ocx/cli or ghcr.io/ocx-sh/ocx/mirror.
  - Never add publishers to ocx-sh/index.

## Issue resolution

Every doubt — an ambiguous requirement, a design question, a failure
with an unclear cause — runs this protocol:

1. Delegate the research to a sub-orchestrator.
2. Record question → research → decision in this file or in the PR.
3. Defer to a GitHub issue only in hard cases — the research ends with no
   decision, or the decision needs an act outside the grants; the issue
   link is the recorded decision.
4. Every doubt not deferred ends in an action.
5. A pre-existing failure that blocks done is in scope and runs this
   protocol.
6. Findings outside this goal's scope become follow-up issues.
7. Secrets and credential-bearing logs are never written to any committed
   file, commit message, PR text, PR comment or review comment, or issue.
   Security findings are never filed as issues:
   this file records them by reference only — location and class, no
   secret value or exploit detail — and only the DONE block reports them
   in full.

## Loop shape

- Entry point: Run the /hex-plan skill on "Signing dogfood, loop A — ocx and ocx-mirror sign their own releases, per .agents/discussions/signing-dogfood.md".
- Refinement rounds: 12 — counts outer cycles: each review ⇄ execute
  pass is one, and so is every failed repair or retry cycle — a red
  gate's fix pass, an execute or finalize retry, a post-finalize CI fix ⇄
  re-finalize pass. Inner review-fix rounds do not count, and their limit
  is untouched.
  Past `12`, the DONE block reports every remaining criterion `not met`
  and the run stops.
- Inner loop: integrate until the end-to-end cases work together (fixes found there are not review rounds), then three to five Sonnet subagents act as end users in isolated environments and try to break it, each bug gets a regression test and a fix, then at most 4 coarse hardening review rounds, and a round that finds only smaller or unrelated issues ends the reviewing.
- Ticks: /hex-loop commits nothing. The session creates or switches to
  the branch the pasted prompt's I9 names and commits this file first on
  it. A box is ticked only between hex-mode runs, never during one, and
  each tick is committed at once; every tick lands before the final
  /hex-finalize, none after it. The `(DONE block only)` criteria are
  evidenced only in the closing DONE block, never ticked.

## Rules

- Run rules:
  - Secrets and tokens are read from the environment and never written to a file, a log or a commit.

## Emphasis

From the source, as pointers; the source's own text governs.

- Order: the dev channel is built first, the ocx release and backfill next, the `ocx-sh/ocx-mirror` port only once the ocx side is green. Existing tags are backfilled before any `publishers` entry reaches a production index, and that entry is not this run's act.
- Non-breaking as the source's `## Intent` defines it: no existing install, config file, published package, index entry, release asset name or install path stops working. The previous ocx release still installs every fixture case it installed before.
- The source's `## Intent` lists what is out of scope: loops B and C (`.agents/discussions/signing-dogfood-index-catalog.md`, `.agents/discussions/signing-dogfood-mirror.md`), index signing, vulnerability scanning, and every production release act.
- A candidate is a production write from `main`, so this run builds the candidate mode and proves it in the fixtures; it never cuts one on the production package.
- The source's `## Open questions` are this run's docket, each with a recommended answer (Bazel stamping, the SBOM generator, the `sdkgen-publish.yml` sign job, pruning dev builds, the packages-API owner type, who creates the dev package, shared or copied workflows, the `publishers` identities). A dev package that starts private is reported as an owner action, not worked around.
- The source's `## Threads` are closed positions; names such as `ghcr.io/ocx-sh/dev/cli` are working spellings open to a better shape with a recorded reason.
- The source's `## Verification` names the acceptance cases; each is shown red on the failing case and green on the passing one. Real-certificate and real-registry cases run in the fixture repositories or on the dev channel, dispatched, never per pull request.
- A new flag on `ocx package prune` is an interface change (`cli.json`, reference pages, exit-code table).

## Context

- Source discussion: `.agents/discussions/signing-dogfood.md` (untracked; read it from the main checkout).
- Parked sibling discussions: `.agents/discussions/signing-dogfood-index-catalog.md` (loop B), `.agents/discussions/signing-dogfood-mirror.md` (loop C).
- Design this builds on: `.agents/discussions/release-signing-trust-default-2026-11-12.md`, `.agents/goals/release-signing-trust-default-2026-11-12.md`, `.agents/loop-security-findings-release-signing.md`.
- Research: `.claude/artifacts/research_signing_dogfood_dev_channel.md`, `.claude/artifacts/research_signing_dogfood_codebase.md`, `.claude/artifacts/research_signing_dogfood_archaeology.md`, `.claude/artifacts/research_signing_dogfood_prior_art.md`.
- Rules and decisions: `.claude/artifacts/adr_bazel_build_adoption.md`, `.claude/rules/workflow-release.md`, `.claude/rules/subsystem-ci.md`.
- Satellite checkout: `/home/mherwig/dev/ocx-mirror` (https://github.com/ocx-sh/ocx-mirror).
- Fixture repositories: https://github.com/ocx-sh/e2e-package and https://github.com/ocx-sh/e2e-index (worktrees `.agents/worktrees/e2e-package`, `.agents/worktrees/e2e-index`).
- Related issues: https://github.com/ocx-sh/ocx/issues/694, https://github.com/ocx-sh/ocx/issues/402, https://github.com/ocx-sh/ocx/issues/403, https://github.com/ocx-sh/ocx/issues/480.

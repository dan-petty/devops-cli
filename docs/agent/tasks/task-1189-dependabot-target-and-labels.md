# Task: Target Dependabot Updates to Main and Configure Taxonomy Labels (#1189)

**Issue**: [#1189](https://github.com/dan-petty/devops-cli/issues/1189)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/ci

## Description
Dependabot updates previously targeted the merged `release/v0.2.26` branch because `.github/dependabot.yml` had hardcoded release version branches. When `release/v0.2.26` was closed, several Dependabot PRs landed on the retired branch while others remained open against it. Additionally, Dependabot PRs failed `devops gh labels audit` because they carried non-standard labels (`dependencies`, `python`, `docker`) rather than the repository's required `type/*` and `scope/*` taxonomy prefixes.

- **Target Dependabot to `main` directly** (`.github/dependabot.yml`). Configured `target-branch: "main"` across all ecosystems (`github-actions`, `pip`, `docker`) without hardcoding ephemeral release branches.
- **Enforce taxonomy labeling on automated PRs** (`.github/dependabot.yml`, `.github/labels.yml`). Registered `scope/ci` and `scope/infra` in `.github/labels.yml` and configured Dependabot to attach `type/chore` along with corresponding `scope/*` labels on all generated PRs.
- **Documentation alignment** (`docs/SDLC.md`, `docs/ROUTINE_TASKS.md`). Documented that Dependabot targets `main` directly and eliminated the obsolete manual task requiring maintainers to update `dependabot.yml` upon cutting release branches.
- **Reconcile merged updates** (`uv.lock`). Cherry-picked the four dependency bumps that merged into `release/v0.2.26` (#1179, #1180, #1181, #1182) and re-locked dependencies.

## Acceptance Criteria
- [x] Dependabot targets `main` across all ecosystem configurations in `.github/dependabot.yml`.
- [x] All Dependabot configurations include valid `type/chore` and `scope/*` labels.
- [x] `scope/ci` and `scope/infra` are declared in `.github/labels.yml`.
- [x] `devops gh labels audit` reports zero non-compliant open PRs.
- [x] `changelog.d/1189.md` records the fix under `### Fixed`.
- [x] Pre-push Gated CI suite (`uv run devops ci`) passes 10/10 checks.
- Pending a person: `uv run devops ci` on this branch; it is this PR's own check, which readiness reads.

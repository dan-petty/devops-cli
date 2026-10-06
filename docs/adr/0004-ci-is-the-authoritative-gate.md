# CI is the authoritative quality gate for merges into release and main

Pull requests merging into `release/*` or `main` must pass automated CI checks to ensure code quality and prevent broken code from landing. The repository uses GitHub repository rulesets that require two checks: `Static Analysis` and `Tests & Coverage`. Strict mode (`strict_required_status_checks_policy: true`) is enabled on both rulesets, requiring pull request branches to be up to date with their base branch before merging. When branches are updated by unattended automation, `.github/workflows/update-prs.yml` runs `devops pr update --dispatch-ci` to dispatch `ci.yml` on the updated head branch; `actions: write` is held only by that job, guarded by the workflow permission allowlist invariant in `tests/test_architectural_invariants.py`. The machine-account token (ADR 0002) is kept strictly inside the Kubernetes cluster Secret (`devops-cli` in namespace `devops`, key `GH_TOKEN` from #741), never in GitHub Actions secrets, ensuring the privileged token lives in only one place. Under owner decision D6, automatic Copilot code review runs on pull requests into `main` only (`review_on_push: false`) to keep LLM token costs bounded; re-reviews on release pull requests are requested on purpose by a person. As an accepted trade-off, item pull requests merged into the release branch after the release pull request opens get no automatic Copilot pass. On the release ruleset, `do_not_enforce_on_create: true` is configured so that branch creation pushes remain unblocked.

## Considered Options

- **Pasting test logs into pull request comments (#704)**: rejected because check run details and artifacts are already authoritative in GitHub Actions; pasting test logs into pull request comments adds clutter, risks credential leakage, and bloats comment history.
- **Per-check scoping / granular matrix required checks (#405)**: rejected because binding rulesets to individual matrix jobs or internal test partitions creates high coupling and breaks whenever runner topologies or matrix dimensions change; top-level aggregating jobs (`Static Analysis` and `Tests & Coverage`) provide a stable, decoupled contract.
- **Mandatory test selection gating (#406)**: rejected; test selection stays advisory rather than acting as a gating constraint, ensuring full test suites run authoritatively on merge gates to prevent untested regressions.

## Consequences

- The `Static Analysis` and `Tests & Coverage` job names are pinned and cannot be altered without coordinating changes to repository rulesets.
- Merges into `release/*` and `main` cannot proceed with failing or missing CI runs, binding unattended roadmap merges.
- Classic branch protection is deprecated in favor of rulesets; `.github/branch-protection.yml` is removed while `devops gh branch-protection` remains scoped to classic protection.

## Friction

The owner asked on 2026-10-23 that a critical security or bug fix releases without waiting for a person to merge the release pull request, with logical labels and rules, and lifted the restriction on agent work on the release files. Today a fix on `main` ships only when a person merges the release-please pull request.

## Evidence

- release-please opens and updates one release pull request, and a person merges it (`.github/workflows/release.yml`, RELEASE_CYCLE.md).
- The repository allows auto-merge (`allow_auto_merge: true`), and the `main` ruleset requires `Static Analysis`, `Tests & Coverage` and `Semantic PR title`, with the strict up-to-date policy.
- The labels `priority/p0-critical`, `priority/p1-high` and `type/security` exist (`.github/labels.yml`), and intake sets them on new issues.
- A merge made with `GITHUB_TOKEN` starts no workflow, so the release App must enable the auto-merge, or the publish run never starts.

## Existing tool considered

GitHub auto-merge (`gh pr merge --auto --squash`, the `enablePullRequestAutoMerge` mutation) merges a pull request when its required checks pass. release-please-action returns the release pull request in its `pr` output. Nothing is built beyond one workflow step.

## Proposed remedy

After `Run release-please`, a step in the same job reads the pull request of the pushed commit and the issues it closes. When one of them is labeled `release/now`, or an issue is labeled `priority/p0-critical`, or `type/security` with `priority/p0-critical` or `priority/p1-high`, the step enables auto-merge on the release pull request with the App token. The label `release/now` joins `.github/labels.yml`. RELEASE_CYCLE.md states the rule, and AGENTS.md drops the agent restriction on the release files. A contract test holds the step, its token, its labels and the documented rule.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=aece067ac6610b68bfe58c8a0de418c03e94519a -->
## Proposed design

### Problem statement
A critical security or bug fix release requires a person to merge the release pull request. This delays urgent releases.

### Acceptance criteria
- Criterion 1: The release pull request auto-merges when an issue labeled 'priority/p0-critical' is closed by the commit.
  Verification: A commit that closes an issue with label 'priority/p0-critical' triggers a workflow step that enables auto-merge on the release pull request.
- Criterion 2: The release pull request auto-merges when an issue labeled 'type/security' with 'priority/p0-critical' or 'priority/p1-high' is closed by the commit.
  Verification: A commit that closes an issue with labels 'type/security' and either 'priority/p0-critical' or 'priority/p1-high' triggers a workflow step that enables auto-merge on the release pull request.
- Criterion 3: The release pull request auto-merges when a commit is labeled with 'release/now'.
  Verification: A commit with label 'release/now' triggers a workflow step that enables auto-merge on the release pull request.

### Key questions
- **What labels exist for critical issues?**: The labels 'priority/p0-critical', 'priority/p1-high' and 'type/security' exist. [sources: .github/labels.yml]
- **What is the release workflow file?**: The release workflow is defined in .github/workflows/release.yml. [sources: .github/workflows/release.yml]
- **Does the repository allow auto-merge on pull requests?**: Yes, the repository allows auto-merge with 'allow_auto_merge: true'. [sources: .github/workflows/release.yml]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Priority": "P1-High", "Status": "Ready", "Value": "High", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "9203330beb6869967372036bcb2fdadcb984f5b2a2d9a489a5b9365578949f65", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "ca40fbc1112359bde35a0a0f701ff74e6dcbc69b4077998c0ab6f430207a724d"} -->

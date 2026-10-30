# Proposal

## Why

#2768: since #2715, intake takes the `type/*` label of an issue only from its Conventional Commit title. `fix(security): ...` gets `type/bug` and `scope/security`, and no title type gives `type/security`. The urgent-fix step of `.github/workflows/release.yml` still reads `type/security` with `priority/p1-high`, so a P1 security fix that intake files does not release at once. `RELEASE_CYCLE.md`, ADR 0013 and the `release-urgent-merge` spec name the same stale label.

## What Changes

- The step `Merge the Release Pull Request on an Urgent Fix` reads `scope/security` with `priority/p1-high` in place of `type/security` with `priority/p1-high`. The `release-now` and `priority/p0-critical` clauses do not change.
- `RELEASE_CYCLE.md`, ADR 0013 and the contract test name `scope/security`.
- The workflow decides when a release merges, which a person observes, so the change carries a delta of `release-urgent-merge`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release-urgent-merge`: An urgent fix turns on auto-merge of the release pull request; The urgent-fix rule is declared and documented.

## Impact

`.github/workflows/release.yml`, `RELEASE_CYCLE.md`, `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md`, `tests/test_workflow_contracts.py`.

## Feasibility

- `CONST_ROADMAP_COMMIT_TYPE_LABELS` in `src/devops_cli/config/constants.py` maps each Conventional Commit type to a `type/*` label, and no type maps to `type/security`.
- The spec `roadmap-intake-title-labels` states that `fix(security): redact a URL user name` gets `type/bug` and `scope/security`.
- `.github/labels.yml` declares `scope/security`.
- The jq filter of the step reads the label names of each closing issue, so a change of the label name is all the step needs.

## Existing Tool Considered

The step already uses `gh api graphql` and `jq`, and GitHub auto-merge does the merge. The change edits one label name and deletes no code.

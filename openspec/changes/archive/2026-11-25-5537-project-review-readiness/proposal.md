# Proposal: #5537

## Why
The production readiness guideline (`docs/guidelines/production-readiness.md`) has 91 rows across 10 areas. Currently `devops roadmap review run` has no readiness section, forcing agents and people to read repository and service evidence by hand across git, GitHub, and CLI checks. Programs must produce repeatable readiness states instead of hand-collected scratch records.

## What Changes
- Add `src/devops_cli/roadmap/project_review/readiness.py` containing:
  - `READINESS_ROWS`: the 91-row map matching every row of `docs/guidelines/production-readiness.md` (its ID, scope, level, check kind, and referenced Scorecard checks / kube-linter checks / CLI commands / file checks), with zero issue numbers and zero gap tables.
  - OpenSSF Scorecard integration (`BIN_SCORECARD = "scorecard"`, `--repo=github.com/<owner>/<name> --format json`) across repositories in `service.repos` and `infra.repos` read dynamically from settings.
  - Scorecard JSON parser mapping scores (`10` -> `met`, `1..9` -> `partly met`, `0` -> `not met`, `< 0` -> `not readable`) and combining multi-check rows cleanly.
  - GitHub contents query reader using `read_github` (`repos/<owner>/<name>/contents/<path>` with optional `?ref=<branch>`) for branch/default-branch file checks (`AGENTS.md`, `CODEOWNERS`, `openspec/config.yaml`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`).
  - `devops` CLI command check executor running `devops ...` commands via `run_subprocess` and mapping JSON stdout (or exit code fallback) to row state.
  - Private-repository privacy guard (excluding private repositories from the shared review output) and GitHub API fallback (`read_github`) when Scorecard fails on a private repository.
  - `not readable` handling with zero external requests for `manual` rows and unread check kinds (`promql`, `catalog`, `settings`, etc.).
- Integrate readiness collection, `--ref`, `--dry-run`, `ReviewData.readiness`, and `render_review` into `src/devops_cli/roadmap/project_review/{data.py,readers.py,review.py}` and `src/devops_cli/commands/roadmap_review.py`.
- Update `docs/guidelines/production-readiness.md` `## Readiness record` to state that the readiness report of `devops roadmap review run` holds the record of a running service and, with `--ref`, of a launch.

## Capabilities

### Modified Capabilities
- `roadmap-project-review`: Add production readiness reporting across `service.repos` and `infra.repos`, Scorecard/GitHub/command readers, `--ref`, private-repository exclusion/fallback, `--dry-run`, and guideline sync checks.

## Impact
- Users of `devops roadmap review run` gain an automated readiness section in `data.json` and human output, plus `--ref <branch>` for launch pull requests.
- Existing `ReviewData.facts` order and contents remain unchanged (`readiness` is added alongside `facts` with an empty default).

## Feasibility
- `src/devops_cli/roadmap/project_review/{data.py,readers.py,dispatch.py,review.py}` and `docs/guidelines/production-readiness.md` exist on `origin/main` (#4692 is merged).
- Unit and integration scenarios run hermetically via `process_fake`, `GitHubApiFake`, and recorded Scorecard JSON fixtures; missing external readers (`catalog` #5535, `settings` #5311, PromQL, kube-linter) and missing live Scorecard binary on private repos fall back cleanly (`not readable` / GitHub API).

## Existing Tool Considered
- OpenSSF Scorecard (`https://github.com/ossf/scorecard`, Apache-2.0, maintained) covers the repository supply-chain and governance checks (`SC <check>`), returning structured JSON. Estimated custom integration cost in `devops-cli`: ~280 lines + tests (~200k tokens, ~1 agent-day).

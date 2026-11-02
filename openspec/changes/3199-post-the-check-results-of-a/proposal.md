# Proposal

## Why

CONTRIBUTING.md requires the check results and the fail-to-pass evidence in a pull request comment, and forbids hand-typed counts. No command writes that comment, so agents typed the numbers into a report or a comment by hand, which can be wrong and differs between pull requests (#3199).

## What Changes

- Add `devops pr evidence <number>` to `src/devops_cli/commands/pr.py`, which posts the check results of the head commit as one comment.
- Add `src/devops_cli/github/pr_evidence.py`, which reads the check runs of the head commit and builds the comment text, so the command and the Service share one builder.
- Keep one comment per pull request by the marker line `<!-- devops-cli:pr-evidence -->`: update it on a new head, and post a new one only when it is absent.
- Take no free text: every count comes from the check runs that GitHub returns.
- Print the comment and the planned requests with `--dry-run`, and send no request.
- End the comment with the attribution footer when an agent runs the command.
- Add a spec delta to `pull-request-form`, because the new command and its message are observable behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pull-request-form`: devops pr evidence posts the check results of the head commit, devops pr evidence keeps one comment per pull request, devops pr evidence takes no free text, The dry run of devops pr evidence sends no request, An agent's comment ends with the attribution footer

## Impact

- Code: `src/devops_cli/github/pr_evidence.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/github/pr_plans.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `CONTRIBUTING.md`, `README.md`
- Tests: `tests/github/test_pr_evidence.py`, `tests/commands/test_pr_evidence.py`

## Feasibility

- The premise holds: no command writes the check-results comment. A search of the command tree of `src/devops_cli/commands/pr.py` shows no `evidence` command, and the module `src/devops_cli/github/pr_evidence.py` is to be created.
- `read_file` of `src/devops_cli/commands/pr.py` showed the command group with `list`, `view`, `checks`, `monitor`, `edit`, `create`, `describe`, `ready`, `diff`, `close`, `check-readiness`, `update`, `hardening-report` and `threads`, and no command that posts a comment.
- `read_file` of `src/devops_cli/github/rate_limiter.py` showed `def run_gh(` at line 1862, the paced runner that the new module calls.
- `read_file` of `src/devops_cli/github/check_verdict.py` showed `fetch_pr_check_verdicts`, which reads the check runs of a pull request through `run_gh`, so the read path exists.
- `read_file` of `.github/workflows/fail-to-pass.yml` showed the job `name: Fail-to-Pass Check` and the step `uv run devops ci fail-to-pass --base "origin/${BASE_REF}"`, and no step that posts a comment. The command must post the comment.
- `read_file` of `src/devops_cli/roadmap/pull_describe.py` showed the attribution footer builder that the command reuses.
- First checks of the implementation against the real system: `uv run devops ci test tests/commands/test_pr_evidence.py`; `uv run devops pr evidence <number> --dry-run` on an open pull request of this repository, which must print the comment and the request plan and send no write request; `uv run devops docs generate --sync-readme`, which must list the new command.

## Existing Tool Considered

No open, maintained tool posts one project-formatted comment per head commit with the fail-to-pass link. GitHub shows the check results on the pull request page, and an action can post a summary, but neither keeps one marked comment per pull request in this form. The written cost to build, keep and fix that code is about 60k tokens and 3 hours; the change deletes no internal code.

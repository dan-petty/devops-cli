# Proposal: #4522

## Why
A scoped intake update, which an `issues` webhook delivery starts, sends its model requests outside a row scope. Thus the AI request, token and spend series of that intake work get `row="other"`, and its GitHub requests get `row="other"` on `devops_cli_github_requests_total`. The job counter of the same update counts row `intake`, so the two do not agree, and `docs/TELEMETRY.md` names intake as a row that sends model requests. Closes #4522.

## What Changes
- `run_scoped_update` in `src/devops_cli/roadmap/run.py` runs the runner of the update in `request_scope(row=update.job)`. The repository of the worker scope stays, because `request_scope` keeps each value that it does not get.
- The row text of `docs/TELEMETRY.md` (from `src/devops_cli/docs/generator.py`) and the docstring of `request_scope` say that a scoped update names its job as the row.
- The change alters the labels of series that the Service sends, which a consumer observes. Thus it has a delta on `roadmap-scoped-updates`.

## Capabilities
- Modified: `roadmap-scoped-updates`.

## Impact
- `src/devops_cli/roadmap/run.py`, `src/devops_cli/github/request_scope.py`, `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`, `tests/roadmap/test_roadmap_run_scoped_update.py`.
- Series: the scoped update has only the job `intake` (`SCOPED_UPDATES`), and `intake` is a row of the due table. Thus no new label value comes, and the series bound of #4475 does not change.
- The change fits one pull request.

## Feasibility
- Source on `main` at 7234d718: `run_scoped_update` calls `update.runner(...)` with no `request_scope`. The only row scope is `with request_scope(row=row.name)` in the round loop of `run.py`. `ScopedRoadmap` in `src/devops_cli/server/service.py` runs the scoped function in `request_scope(repo=self.repo)` only.
- `track_request_spend` in `src/devops_cli/ai/spend/ledger.py` reads `request_labels()["row"]` for the request, token and spend series.
- Run on the base: `test_the_model_requests_of_a_scoped_intake_carry_the_intake_row` sends an `issues.opened` delivery through the real `GatewayIntakeModel` and `LLMClient` over the `web` fake, and the `otlp` fake reads `row` `other` on the three series. With the change, it reads `intake`.

## Existing Tool Considered
- The `request_scope` context manager of `devops_cli.github.request_scope`, which the round loop already uses, covers the need. No new tool or library is needed, and the change deletes no code.

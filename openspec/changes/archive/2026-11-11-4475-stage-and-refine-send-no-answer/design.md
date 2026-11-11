# Design

## Decisions
- **Count at the request.** The ledger writes one row for each request since #4237, so the hook counts each reply in the same place. A run does not count a second time: only the implement step calls `record_run_spend`, and its agent has no hook of `build_agent`.
- **One label helper.** `model_answer_labels` holds the fallback rule (#4205) and the row. `record_run_spend` changes only its label dictionary, so the hunk stays small.
- **The row comes from `request_scope`.** The Service already names each row there for `devops_cli_github_requests_total` (#2475), and the context variable reaches the worker threads of the run. A second scope for AI would hold the same value.
- **The runner Job names its row.** The Service row `implement` only starts Jobs, and the model requests run in the Job. The command wraps `apply_implement` in `request_scope(row="implement")`, so the Job's GitHub requests also count under that row.

## Rejected alternatives
- **Call `record_run_spend` again in `investigate`.** It writes a second ledger row for each run and counts the tokens two times.
- **A `row` column in the ledger.** The task asks for the series; #594 plans a change of the ledger structure.
- **A fixed list of rows (intake, refine, alternatives, stage, implement).** The scope already holds the due-table rows and `other`; a second list would drift from the table. `retitle` also sends model requests.

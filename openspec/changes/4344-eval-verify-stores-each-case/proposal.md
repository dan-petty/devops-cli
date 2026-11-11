# Proposal: #4344

## Why

`devops roadmap eval verify` runs one agent review for each case of the golden set and writes its report only when the last case ends. A run of the 48 cases takes about two hours and costs about 8 USD (2026-11-10). If the process stops in the middle, the run loses every case that ended. On 2026-11-10, 6 of 48 cases failed with `ModelConnectionError`, and each one had to run again in its own process, with no way to merge the results except by hand. The recall study of the reviewer (#4402) needs repeated runs. Closes #4344.

## What Changes

- The run writes the report file at the start and again when each case ends. Each write replaces the whole file atomically (`write_text_file`), so the file is always a complete report of the cases that ended.
- The new option `--resume <report>` reads a report of the command and runs only the cases that the report lacks or that failed in it. It keeps the other cases unchanged, merges them with the new outcomes into one score, and updates the same file. The cases of the run are the cases that `--case` and `--limit` select and the cases of the report, so a resume never drops a case from the file.
- A resume of a report of another model, of a report with a case that the set lacks, or of a file that is not a report stops before any model call with a `ConfigurationError`.
- The command names the report file when the run starts, so a person can resume a stopped run.
- The score is a function of the cases and the outcome of each case (`verify_score`). The evaluator `Recall` goes: the run computes the matched defects of a case from its findings, both for a new case and for a case of a stored report.
- `--dry-run` with `--resume` lists only the cases that would run.

This change alters the behavior of a command and adds an option, so it carries a spec delta.

## Capabilities

- `roadmap-stage-eval`: five ADDED requirements (the command stores each case when it ends; each write leaves a complete report; rejected credentials keep the cases that ended; the command resumes a stored report; a resume refuses a report that it cannot merge) and one MODIFIED requirement (the group lists `--resume`).

## Impact

- `src/devops_cli/roadmap/stage/stage_verify_eval.py`: `verify_score`, `resumed_outcomes`, the `done` and `store` arguments of `evaluate_cases`, and a `CaseLifecycle` hook that gives each case to the caller when it ends.
- `src/devops_cli/commands/roadmap_eval_verify.py`: the `--resume` option, the line that names the file, and the write after each case.
- `src/devops_cli/lang/en/`: the help of `--resume` and four messages.
- `docs/ROADMAP_WORKFLOW.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`.
- The JSON format of the report does not change, so `devops roadmap eval screen --reviewer` reads a stored or resumed report as before.

The change fits one pull request.

## Feasibility

- `pydantic_evals` 2.59.0 (the locked version) takes `lifecycle=` in `Dataset.evaluate_sync`. `CaseLifecycle.teardown(result)` runs once for each case after the task and the evaluators, with the `ReportCase` or the `ReportCaseFailure` of the case, or with `None` when the run ended with no result, such as a stop (`pydantic_evals/lifecycle.py`, `pydantic_evals/dataset.py` `_run_task_and_evaluators`). The hook gives each case to the caller when the case ends, with no change to the library.
- A sync task runs in a worker thread (`anyio.to_thread.run_sync`). A `BaseException` in the task passes the `except Exception` of the library, so `teardown(None)` runs and the stop reaches the caller. The test `test_a_stop_in_the_third_case_keeps_the_two_cases_that_ended` shows that the stop reaches the caller inside a `BaseExceptionGroup` of the task group, and that the two cases that ended are stored.
- `verify_json` already lists each case with `name`, `good`, `labeled`, `found`, `returning`, `error` and `findings`, which are the fields of `CaseOutcome`. pydantic validates the stdlib dataclass `CaseOutcome` and the `Finding` model of each finding from that JSON, so the reader adds no new format.

## Existing Tool Considered

`pydantic_evals` (open, maintained, locked at 2.59.0) runs the cases. Its `Dataset` has no resume and no store of a report, but its `CaseLifecycle` hook gives each case when it ends, so the change uses that hook in place of a hand-made wrapper around the task. The atomic write is the existing `devops_cli.output.write_text_file`. The reader of a stored report is a pydantic model over the format that `verify_json` writes. The rest is code in this project: the merge of stored and new outcomes and the `--resume` option. Written cost: about 60 000 tokens and 2 hours to build, and about 5 000 tokens to keep the reader in step with `verify_json`, which lives in the same module.

The change deletes the evaluator `Recall` and `_recall_scores`, and the code that read the scores of the `pydantic_evals` report into the score, because `verify_score` now computes the score from the outcome of each case.

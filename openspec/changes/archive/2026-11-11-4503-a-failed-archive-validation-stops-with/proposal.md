# Proposal

## Why

When the strict validation of the specs fails after the archive of the implement job, the stop has the class `test` and the action left `repair`. No test failed, and no fix step runs after a failed project program, so nothing acts on that stop. Closes #4503.

## What Changes

- The archive step of the implement job passes the class `plan_defect` when `uv run devops openspec archive <change>` exits with status 1 after it moved the change folder into the archive. That is the case where `openspec validate --all --strict` refused a spec that the change wrote. The default action of `plan_defect` is `amend`: change the plan of the item.
- An archive that fails before it moves the folder, or that a signal or a timeout ends, keeps the class that the classifier gives.
- `failure.py` does not change: the class and its action come from `ACTION_BY_CLASS` as they are.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: A spec that the archive validation refuses is a plan defect (added)

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_run.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_job.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- The change fits one pull request.

## Feasibility

The line numbers are those of `main` before this change.

- The stop comment on #3462 (`devops gh api repos/dan-petty/devops-cli/issues/3462/comments`) says "Stopped at archive.", "Failure class: `test`.", "Action left: `repair`", and holds "Totals: 258 passed, 1 failed (259 items)", "✗ spec/roadmap-stage" and "The archive is applied".
- `archive_change` runs `openspec archive <change> --yes` and then `openspec validate --all --strict` (`src/devops_cli/openspec/archive.py:30`). It raises `ToolExecutionError` when the validation fails (`archive.py:69`), so `devops` exits 1 after the move.
- `_program` raises `_StopError` with the exit status and no class (`src/devops_cli/roadmap/implement/implement_run.py:677`). The archive step calls it with no class (`implement_run.py:1227`).
- `classify_failure` reads the text rules of the checks before the name of the check (`src/devops_cli/roadmap/failure.py:336`, `failure.py:345`). The `test` rule matches `\d+ failed\b` (`failure.py:288`), so "1 failed", a count of specs, gives `test`.
- `ACTION_BY_CLASS` gives `plan_defect` the action `amend` (`failure.py:123`). The Service clears only a stop whose action is `retry` (`src/devops_cli/roadmap/stop_clear.py:198`), so a `plan_defect` stop waits for a person who changes the spec and comments `implement: retry`.
- A test on the base reproduces the defect: an archive that moves the folder and exits 1 with the output of #3462 records `implement.failure` `test`.

## Existing Tool Considered

The failure taxonomy of the project (`failure.py`) covers the need: the class `plan_defect` and its action `amend` exist, and the spec of the implement job already says that a stop site that knows its cause passes its class. The site reads the result on disk, as `archive_change` does (#4270). OpenSpec gives no exit status that tells a validation failure from an archive failure, because `devops openspec archive` runs both. The change adds no library and no class. Cost: about 15k tokens to build, 2k to keep and fix, about 1 hour.

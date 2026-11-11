# Proposal: #4535

## Why

No log line shows what a fix loop of the roadmap jobs did, so the pass rate of a return cannot be measured (#4535). The stage job logs each refused reply, but not a reply that passed after a return, not a review round, and not a failed item. The implement row reports an ended Job only in a comment and in metrics. The error line of a round keeps only the first line of an error, cut at 256 characters, so a long reason of the first failed item hides the others: a study of 48 hours of Service logs found 433 of 628 failed items in the failure lines.

## What Changes

- The new module `src/devops_cli/roadmap/round_log.py` writes four log lines with counts and no model text: `stage gate returns`, `stage review round`, `stage item failed` and `implement attempt`. Each line ends with `version=<devops-cli version>`. `implement attempt` also names the runner digest that the item record holds.
- `_returned` and `_verified` in `stage.py` log the returns and each review round. The `stage` row of `run.py` logs each failed item. `_report` in `implement_submit.py` logs each ended Job.
- `_format_error_line` in `run.py` adds `(failed items: #<n>, ...)` after the cut line of an error that has `failed_items`.
- `_emit_implement_metrics` reads the repair rounds with the new `_repair_rounds`, which deletes a `try`/`except` that ignored an error.
- The log lines and the error line are output of the Service that a person reads, so the change has a spec delta.

## Capabilities

- `roadmap-service-logs`: ADDED requirements "Each fix round and each failed item logs one line with counts" and "The error line of a round names every failed item".

## Impact

- `src/devops_cli/roadmap/round_log.py` (new), `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/implement/implement_submit.py` and `k8s/README.md`.
- A stage round logs at most a few lines more for each item that it plans. No metric changes.
- The change fits one pull request.

## Feasibility

Confirmed on origin/main 5f75d256: `_returned` (`stage.py`) returns the outcome of a passed reply with no log line, `_verified` calls `_review` once and then once for each repair round, `_report` (`implement_submit.py`) reads `implement.job_digest` for its comment, and `_format_error_line` (`run.py`) returns `mask_secrets(first)[:256]`. `RoadmapStageError` holds `failed_items`.

The issue asks for the Service image digest on each line. The Service process cannot read its own digest with no Kubernetes API request (the Downward API gives no image). The release workflow (`.github/workflows/release.yml`) builds the Service image only for a release, with the release tag and `latest`, so the devops-cli version names one image. The stage lines therefore carry the version, and the implement line carries the runner digest that the item record already holds.

## Existing Tool Considered

The standard `logging` module and the JSON log lines of the Service, which Loki reads, cover the need. The change adds no tool.

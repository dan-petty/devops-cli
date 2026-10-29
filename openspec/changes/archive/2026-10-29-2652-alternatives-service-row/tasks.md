# Tasks

## 1. The Service runs the check once a day

- [x] 1.1 Write the tests for the Service row in `tests/test_roadmap_run.py` (the row follows `refine`, a first run, the interval, no webhook hint, the limit of the setting, a failed check, the dry run's `Due:` line) and for the setting and the command's default limit in `tests/test_roadmap_alternatives.py`, and verify that `uv run devops ci test tests/test_roadmap_run.py tests/test_roadmap_alternatives.py` fails because the row and the setting do not exist
- [x] 1.2 Add `DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES` in `src/devops_cli/config/defaults.py`, the setting `roadmap.alternatives.limit` in `src/devops_cli/config/settings.py`, the row and its runner in `src/devops_cli/roadmap/run.py` (with `include_alternatives` in `build_stub_table`), and the default of `--limit` in `src/devops_cli/commands/roadmap.py` and `plan_alternatives`, and verify that `uv run devops ci test tests/test_roadmap_run.py tests/test_roadmap_alternatives.py` passes

## 2. The metric

- [x] 2.1 Write the tests for `devops_cli_roadmap_alternatives_total` in `tests/test_roadmap_alternatives.py` (one point for each written check by verdict, none for a plan, none for a skipped check) and verify that `uv run devops ci test tests/test_roadmap_alternatives.py` fails because the instrument does not exist
- [x] 2.2 Add the instrument in `src/devops_cli/telemetry/instruments.py` and emit it in `apply_alternatives` in `src/devops_cli/roadmap/alternatives.py`, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py tests/test_metric_instruments.py` passes

## 3. Refine uses the recorded check

- [x] 3.1 Write the tests in `tests/test_roadmap_refine.py` for the hash of the body (an item with a block reads as unchanged after a round, and a block written during the round is kept), the `alternatives` key of the request, the `covers` question (no reply, a reply and an answer, a reply and no answer, a `person` answer, a `partly` check), and the second look (a Ready item, the same tool, a waiting item and a new tool), and verify that `uv run devops ci test tests/test_roadmap_refine.py` fails for each reason
- [x] 3.2 Move `Verdict` to `src/devops_cli/roadmap/store.py`, add `RefineRecordKey.ALTERNATIVES_ASKED`, and make refine in `src/devops_cli/roadmap/refine.py` hash the body without the block, read the recorded check, add the `covers` question, select the item for a second look and record the tool it asked about, with the messages in `src/devops_cli/lang/en/messages.py` and the prompts `roadmap_refine_proposal.md` and `roadmap_refine_investigation.md`, and verify that `uv run devops ci test tests/test_roadmap_refine.py tests/test_roadmap_alternatives.py` passes

## 4. Documentation

- [x] 4.1 Name the row in `CONTEXT.md` (Lane) and in `k8s/README.md` (Roadmap service), regenerate the documents with `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes
- [x] 4.2 Run `uv run devops ci` once, fix each failure at its cause, and verify that it passes
- [x] 4.3 Fix the review findings test-first in `tests/test_roadmap_refine.py` (no job comment, a reply that refine's later comment hides, a comment of another job) and verify that `uv run devops ci test tests/test_roadmap_refine.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

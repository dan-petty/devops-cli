# Tasks

## 1. Read the totals of the last implement run from the trace

Reads: `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/implement/implement_trace.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_explain.py`.

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_explain.py`: a record that holds a trace with one model event of 1200 in, 300 out and 90 s and two attempt events (`failed` then `repair`, `passed` then `stop`) gives 1500 tokens, 90 s, 1 repair round, 1 failed and 1 passed in `explain_item(...).totals` and in `render_explanation`; a trace with 12 dropped events adds the dropped line; a record with no trace gives no totals and says so. Update the two tests that pin the report lines to the new last lines
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_explain.py` fails on the base
- [x] 1.2 Add `TraceTotals` and `trace_totals` to `src/devops_cli/roadmap/explain.py`: sum `tokens_in` and `tokens_out` and the `seconds` of the model events, round the seconds to one decimal, count the attempt events by `outcome`, count the attempt events whose `next` is `repair`, and keep `dropped`. Add `totals` to `Explanation`, filled in `explain_item` by decoding `ImplementRecordKey.TRACE` of the item it already read, through the same decode as `read_trace`. Append the totals line, the dropped line and the no-record line in `render_explanation`. Add the three texts to `RoadmapMessages`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_explain.py` passes

## 2. Print the totals as a JSON object with --json

Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_explain_command.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_explain_command.py`.

- [x] 2.1 Write failing tests in `tests/roadmap/test_roadmap_explain_command.py`: `explain <item> --json` prints an object with `tokens_total` 1500, `seconds_total` 90, `repair_rounds` 1 and `outcomes` of 1 failed and 1 passed for a fixture record, and the same run without `--json` prints those values as text; a record with no trace gives null for each total; `--json` with `--trace` exits 1 and names both options
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_explain_command.py` fails on the base
- [x] 2.2 Add `Explanation.as_dict`, which returns the number, the four totals, the outcomes and the dropped count, with null for each total when the record holds no trace. Add the `--json` option to `explain_cmd` and print `json.dumps(explained.as_dict())` when it is set. Refuse it together with `--trace` through `_refuse` and the new message `explain_json_with_trace`. Add the help text of the option to `HELP.roadmap` and the refusal message to `MESSAGES.roadmap`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_explain_command.py` passes

## 3. Document the totals and the new option

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/commands/roadmap.md`, `src/devops_cli/lang/en/help.py`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`, `README.md`.

- [x] 3.1 Edit the `devops roadmap explain` note of `docs/ROADMAP_WORKFLOW.md` to say that the command reports the tokens, the seconds, the repair rounds and the outcome counts of the last implement run, the count of dropped events, and the totals as a JSON object under `--json`. Run `uv run devops docs generate --sync-readme` so that `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md` and `README.md` hold the new help text and the new option
  - Verification: `uv run devops docs check` passes
- [x] 3.2 Edit `docs/ROADMAP_WORKFLOW.md`, then regenerate `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md` and `README.md` with `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

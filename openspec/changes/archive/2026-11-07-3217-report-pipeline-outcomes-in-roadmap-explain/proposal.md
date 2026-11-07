# Proposal

## Why

`devops roadmap explain` says yes or no for each job and names the first rule that stops it, and it reports no totals of the last implement run. A person cannot read the outcome counts, the duration, the repair rounds or the tokens of one item, and no test can compare a dashboard panel value with the command (#3217).

## What Changes

- `src/devops_cli/roadmap/explain.py` gains `TraceTotals` and `trace_totals`, which sum the model events and count the attempt events of the trace of the last implement run.
- `src/devops_cli/roadmap/explain.py:class Explanation` gains `totals`, which `explain_item` fills from the issue that it already reads, so the command makes no second read.
- `src/devops_cli/roadmap/explain.py:def render_explanation` prints the tokens, the seconds, the repair rounds, the outcome counts and the count of dropped events, or says that the item has no recorded run.
- `src/devops_cli/commands/roadmap.py:def explain_cmd` gains `--json`, which prints the same totals as a JSON object, and refuses it together with `--trace`.
- `src/devops_cli/lang/en/help.py` and `src/devops_cli/lang/en/messages.py` hold the new texts.
- `tests/roadmap/test_roadmap_explain.py` and `tests/roadmap/test_roadmap_explain_command.py` assert the totals of a fixture trace, the JSON object, the nulls of an item with no trace and the count of dropped events.
- `docs/ROADMAP_WORKFLOW.md` names the totals and `--json`, and `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md` and `README.md` are generated again.
- The change carries a spec delta on `roadmap-explain`, because the output of a command is observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-explain`: Totals of the last implement run, The JSON object gives the same totals, Item with no recorded run, Dropped events beside the totals, The command makes no model call and no write

## Impact

- Code: `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`, `README.md`
- Tests: `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_explain_command.py`

## Feasibility

- The probes confirm the three cited paths: "The path `src/devops_cli/roadmap/explain.py` is a file of the staging commit.", "The path `src/devops_cli/commands/roadmap.py` is a file of the staging commit." and "The path `tests/roadmap/test_roadmap_explain.py` is a file of the staging commit."
- The probes show two cited paths that moved: "These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_trace.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it." The same holds for `src/devops_cli/roadmap/stores/store.py`. The plan uses the new paths and plans no code for the old ones.
- "The path `implement.trace` is no file of the staging commit." It is no path: it is the key of the job record that holds the trace, `ImplementRecordKey.TRACE` of `src/devops_cli/roadmap/stores/store.py`, which `src/devops_cli/roadmap/explain.py:def read_trace` reads.
- `file_symbols` of `src/devops_cli/roadmap/explain.py` showed `def explain_item` at line 174, `def render_explanation` at line 231 and `def read_trace` at line 254: the module that the plan extends holds the verdicts and the one trace reader.
- `read_file` of `src/devops_cli/commands/roadmap.py` lines 855-925 showed `src/devops_cli/commands/roadmap.py:860:def explain_cmd(` with the options `--repo`, `--source`, `--filter`, `--limit`, `--trace` and `--dry-run`, and no `--json`; line 914 prints `write_stdout(render_explanation(explained) + "\n")`.
- `read_file` of `src/devops_cli/roadmap/implement/implement_trace.py` lines 97-175 showed `src/devops_cli/roadmap/implement/implement_trace.py:def model_call` writing `tokens_in`, `tokens_out` and `seconds`, and `src/devops_cli/roadmap/implement/implement_trace.py:def attempt` writing `outcome` of `failed` or `passed` and `next` of `repair` or `stop`: the trace holds every total that the report needs.
- `search_code` for `explain_trace_dropped` returned `src/devops_cli/lang/en/messages.py:2162:explain_trace_dropped: str = "{count} earlier event(s) are not kept."` and `src/devops_cli/roadmap/explain.py:333`, so the dropped count is printed by `--trace` today and the report can name it too.
- `read_issue` of #3851 showed it open, with "This part waits on #3217, which adds the totals to `explain` output." The refine block of this issue states "The dashboard panel agreement test leaves this item. The panels are totals by repository and class, so no panel value equals one item's value." The plan delivers the totals and plans no panel test.
- `read_issue` of #3069 showed it open and that it adds Service metrics and a repair-round count in the job record. The trace already holds that count, so this plan needs no field from #3069.
- `explain_item` needs a checkout of the repository, which it passes to the reads of git, and a client of GitHub through the store that it reads.
- `read_remote_heads` needs a checkout of the repository, and `read_planned_changes` needs a checkout of the repository.
- `read_trace` needs a client of GitHub, because it reads the issue that holds the record, and `RoadmapStore.item` needs a client of GitHub for the same reason.
- `get_roadmap_store` needs a client of GitHub, and `model_clone` needs a network, because it clones the repository.
- `decode` needs no checkout, no client and no network: it reads the text of the record.
- The first checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_explain.py`, `uv run devops ci test tests/roadmap/test_roadmap_explain_command.py`, `uv run devops docs check`, and `uv run devops roadmap explain 3217 --json` on a checkout, which needs a client of GitHub and a network.

## Existing Tool Considered

jqlang/jq is open and maintained and sums the fields of a JSON document offline, but it does not read the job record of the item from the issue body and it does not render the text and the JSON of the command. Written cost: 12k tokens to build the report and its JSON object, 3k tokens a year to keep and fix it, and 4 hours of elapsed time.

## Dependencies

None.

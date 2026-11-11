# Proposal: #4463

## Why

The Feasibility trace gate refuses plans that cite a file that the run read (#4463). `_claimed_path` in `src/devops_cli/roadmap/stage/stage_change.py` gets the path of a code span only from the forms `path:N:text` and `path:def name`. Planners also write `path:N-M`, `path:N`, a toolbox tool name before the path (`read_file path`) and a directory with a trailing `/`. The gate then compares the whole span with the read paths, finds no match and refuses the plan. The gate also reads a claim from a probe line that the plan quotes word for word, although the content gate asks the plan to quote a probe line. The trace and citation gates are the largest active cause of stage refusals, and three earlier fixes did not stop them. Closes #4463.

## What Changes

- The trace gate takes the path of a `path:N` and a `path:N-M` citation, as it does for `path:N:text` and `path:def name`.
- The trace gate removes a toolbox tool name before the path of a code span. The names come from `tool_names(HOLDER_STAGE_EXTENDED)`, the list that the gate already uses for tool claims.
- The trace gate removes a trailing `/` from a claimed path and from a path that the run read, so a directory that the run listed matches.
- The trace gate removes each sentence of the probe lines from a Feasibility sentence before it reads the claim, so a quoted probe line makes no claim. A claim beside the quote is still judged.
- A path that the run did not read stays refused in each form, and the refusal names the path without the line numbers or the tool name.
- The change carries a spec delta, because it changes which plans the stage job refuses. It fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The trace gate reads the path of each citation form

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`

## Feasibility

- The premise is confirmed on the stored refusals. The Service keeps the refused replies of the last run of each item as `<n>.refused.json` (`src/devops_cli/roadmap/stage/stage.py:def _keep_refused`). On 2026-11-11 it held 19 records. 11 replies of 9 items hold 32 trace refusals. I counted the form of each refused path: 14 `path:N-M`, 1 `path:N`, 3 a tool name before the path, 1 `path:def name` (a run before #4299), and 13 a bare path. So 18 of 32 use a form that `_claimed_path` cannot match. 6 of the 13 bare paths come from a quoted probe line.
- Three real examples from the records:
  - #4412: "`read_file` of `src/devops_cli/roadmap/run.py:770-861` shows the 11 rows." was refused as "The Feasibility section states that `src/devops_cli/roadmap/run.py:770-861` was read, but the run did not read it." In the same reply, the gate accepted "`read_file` of `src/devops_cli/roadmap/run.py` lines 400-560 shows ...", so the run read the file.
  - #3398: "`read_file src/devops_cli/github/merge_readiness.py` lines 541 to 577 showed that `assess_merge_readiness` judges the mergeable state ..." was refused as `read_file src/devops_cli/github/merge_readiness.py`.
  - #4442: "The probe of the stream type reads, word for word: The path `src/devops_cli/ai/client/network.py` is a file of the staging commit." was refused as `src/devops_cli/ai/client/network.py`.
- The Service log (Loki, 2026-11-09 to 2026-11-11) holds 78 trace refusals of the last replies of 32 items. Of these, 12 are `path:N-M` and 2 are a directory with a trailing `/` (`tests/telemetry/` of #3532 and `src/devops_cli/ai/tasks/` of #3599). The 35 `path:N:text` and `path:def name` refusals are all from runs up to 2026-11-10 01:51 UTC, before #4299 was live.
- The gate has the probe lines: `check_gates` receives `probes` and gives them to the content gate (`content_problems`), and the job fills them from `request.probe_lines`.
- First check against the real system: `uv run devops roadmap eval stage --replay` on the base and on the change gives the same report: 81 of 318 defects caught by a gate, 0 missed, and 5 of 5 good plans accepted.
- Second check: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_spans.py tests/roadmap/stage/test_roadmap_stage_trace_subject.py`.

## Existing Tool Considered

No library reads the path of a citation in the forms of this project's prompt. The change adds two forms to the pattern `_CITATION_PATH`, reads the tool names from the existing toolbox list, and removes the probe sentences that the gate already receives. Cost: about 25 000 tokens to build, 3 000 to keep and 1 hour. The change deletes no internal code.

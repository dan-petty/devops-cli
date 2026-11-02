# Design

## Decisions

- **Each limit has a class, in a table that a test holds.** The classes are `raised` (a cap that cut work, now far higher), `guard` (the loop guard of a job), `window` (a share of the context window, or a number that must fit it), `setting` (a number that a person tunes), `kept` (an outside system, a reader or the memory sets it) and `other` (a schedule or a policy value). The table is `LIMITS` in `tests/roadmap/test_roadmap_limit_classes.py`. The test reads the numeric `CONST_ROADMAP_*` and `DEFAULT_ROADMAP_*` values of `config/constants.py` and `config/defaults.py`, and fails for a limit with no entry and for an entry with no limit. A second list, `REMOVED`, holds the names that left the code and must not return.
- **The time limits are settings.** `roadmap.implement.request_timeout_seconds` (1200), `command_timeout_seconds` (1800) and `monitor_timeout_seconds` (3600) are fields of `RoadmapImplementConfig` with `Variable()`. The defaults are `DEFAULT_ROADMAP_IMPLEMENT_*_TIMEOUT_SECONDS`. Each reader asks `load_settings()` when it runs, as `repair_rounds` does. The call deadline stays under the router timeout of the gateway (1500 s) by default; a test holds this. A person who sets a value above 1500 s gets the router stop first, and the field description says so.
- **The output cap of a reply is a share of the window.** `output_cap(window)` is the window divided by `CONST_ROADMAP_IMPLEMENT_OUTPUT_WINDOW_SHARE` (4): 32000 tokens of 128000. The longest reply that was measured is 11634 tokens, so the cap still cuts only a model that does not stop. The prompt keeps its advice to write a long file in parts.
- **The stage run has no count of output tokens.** The output of every request is in the messages of the run, and the window hook removes the tools before the messages pass the window. A count of output tokens guarded nothing more. A single endless reply would not be stopped by that count either, because pydantic-ai checks the usage after a response is whole.
- **The counts of requests and calls stay as the loop guard.** `_within_budget` reads both counts and treats `None` as "no tool", so the counts must stay set. Each job keeps one pair, raised 6 to 8 times: a model that calls tools in a loop still ends in minutes and not at the Job deadline. The window ends a stage run and a refine run first, at about 30 requests on a window of 65536 tokens.
- **Refine and the alternatives check pass the window to `investigate`.** Until now only the stage run did. With counts of 100 and 150, a run on a small window would have sent a request longer than the window. `analysis_window()` moves to `refine_investigation.py`, and `stage.py` imports it.
- **The step budget is half of the implement window.** `DEFAULT_ROADMAP_STAGE_STEP_TOKENS` is `DEFAULT_AI_IMPLEMENT_CONTEXT_WINDOW // 2` (64000). The turn reserve is 40000 tokens, so the inputs and the reserve use 104000 of 128000. A test holds the sum. The packed file of a step is 8000 tokens, a sixteenth of the window.
- **Tool answers rise by the same factor as the files.** A refine tool answer is 8000 characters (about 2000 tokens) and 240 lines; the stage tools follow (40 commits, 40 mapped files of 180 characters, 16000 characters of spec text). A test holds that the lines of the map fit one answer.
- **The verification pass keeps its caps.** Its slot sets no window, the default of 32768 tokens is below what the caps allow, and any raise needs a configured window first.

## The table

| Limit | Old | Now | Class | Reason |
| :--- | :--- | :--- | :--- | :--- |
| Model call deadline | 600 s | 1200 s, setting | setting | Under the router timeout of 1500 s; covers a reply at the new cap |
| Command timeout | 900 s | 1800 s, setting | setting | A command is a verification, a check or a hook |
| Watch of the checks | 1800 s | 3600 s, setting | setting | A check of CI that takes more than 5 minutes is a defect, so an hour is an outer bound |
| Output cap of a reply | 16384 tokens | window / 4 (32000) | window | Cuts only a model that does not stop |
| Stage output tokens | 50000 | none | removed | The window holds the messages |
| Stage tool calls and requests | 30 and 40 | 200 and 250 | guard | The window ends the run first |
| Refine investigation requests and calls | 12 and 20 | 100 and 150 | guard | The window ends the run first |
| Implement requests and calls | 80 and 240 | 500 and 1500 | guard | The Job deadline is the only other stop |
| Step budget | 40000 tokens | 64000 | window | Half of the implement window |
| Packed file of a step | 3000 tokens | 8000 | raised | A sixteenth of the window |
| Tool result of a step | 16000 chars | 40000 | raised | A twelfth of the window |
| Log of a failed check | 6000 chars | 20000 | raised | The inputs of a fix step are measured against the window |
| Refine tool answer | 4000 chars, 120 lines | 8000, 240 | raised | The window hook guards the run |
| Stage log, map, spec answers | 20, 20, 8000 | 40, 40, 16000 | raised | Follow the tool answer |
| Alternatives searches, reads, body | 3, 6, 4096 tokens | 10, 30, 16384 | raised | The body is a quarter of the planner window of 65536 |
| Refine web searches | 3 | 10 | raised | |
| Refine specs, requirements per spec | 5, 40 | 10, 100 | raised | A plan needs the requirement names for MODIFIED |
| Refine replies, reply size | 5, 1024 tokens | 10, 4096 | raised | A reply of a person is not cut early |
| Refine body | 65536 chars | same | kept | GitHub holds an issue body of 65536 characters |
| Pull request body | 1000 chars | same | kept | The rule of the project |
| Stop report: diff, reason, last message | 20000, 4000, 1500 chars | same | kept | One comment holds 65536 characters and a person reads it |
| Masking reads | 4 times the cut | same | kept | The masking of secrets is slower than linear |
| Verification body, file, files | 6000, 1500, 30 | same | kept | The slot sets no window; its default is already below the sum |
| Comments of refine per item | 2 per 24 h | same | kept | Stops a loop of replies with another bot |
| Retries of a broken reply, refused tool call, resends | 2, 5, 1 | same | kept | A model that repeats the same fault is stuck |
| Scoped test modules | 30 | same | kept | Bounds the run time; the required checks of CI run the rest |
| Repair rounds | 3 | same | setting | Already a setting; each round is a real attempt |
| Items of a round, intake sizes, schedules | | same | kept, other | A round and a schedule are not a cut of a run |
| Job deadline, admission policy, Role, memory | | not touched | kept | Owned by the Job deadline issue (#3063) |

## Rejected alternatives

- **Remove the request and tool call counts.** `_within_budget` of `refine_investigation.py` reads them and offers no tool when a count is `None`. The Job deadline would be the only stop of a looping model, and it takes two hours. Evidence: `limits.tool_calls_limit or 0` in `_within_budget`.
- **Keep the old counts until a cost budget exists.** The owner said that the spend is small (the DeepSeek route cost 1.42 USD since it was enabled), so cost is no reason to keep a cap.
- **A tool answer share of the window by formula.** Each tool would read the window at run time, and the constants would no longer be plain numbers in a table. The window hook already guards the run, so plain larger numbers are enough.
- **Raise the router timeout of the gateway.** It is a cluster setting that a person changes (`k8s/llm/gateway/config.yaml`). The new default fits under it.
- **Raise the caps of the verification pass.** The slot has no window setting. Evidence: the example ConfigMap sets a window for `analysis` only.
- **One setting for all three time limits.** A model call, a command and a CI watch have different causes of delay, so a person tunes them apart.

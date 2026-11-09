# Proposal: the window estimate of a run tracks the real input

## Why

A stage run took its function tools from the model too early (#4221). `tokens_of` counts the JSON dump of the messages with tiktoken. The count is higher than the input that the provider reports, so `_limit_reached` reached `tool_stop(window)` while the real input was still far below it. In the live run of item 3599, the real input of request 13 was about 105,000 tokens and the limit for a window of 200000 is 150,000. Request 14 still offered only `final_result`, and the run lost about 45,000 tokens of room for reading.

## What Changes

- `tokens_of` in `src/devops_cli/roadmap/refine/refine_investigation.py` takes the input of the last reply from its usage (`input_tokens` plus `output_tokens`), and adds the count of the text parts of the messages that came after that reply. With no reply yet, or with a reply that reports no input, it counts the text parts of all messages: the instructions, the user prompts, the tool calls and the tool answers. It does not count their JSON form. It uses no fixed factor.
- `_limit_reached` and `stage_verify._request_tokens` keep the same call. The first request of a review run counts less than before, so the tests that name its size change with it.
- The retry for a call to a tool that is not offered is not changed. See Feasibility: the premise of the third expected point is false.
- New tests in `tests/roadmap/refine/test_roadmap_refine_investigation_window.py` (the estimate, the limit and the first request) and one guard test in `tests/roadmap/refine/test_roadmap_refine_investigation.py` (the retry text names the offered tools).
- Acceptance criteria 3 and 5 of the issue are not delivered. Criterion 3 is refuted by the evidence below. Criterion 5 needs a live model call and is a check for a person after the release.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A plan run keeps its messages inside the context window

## Impact

- Code: `src/devops_cli/roadmap/refine/refine_investigation.py`.
- Tests: `tests/roadmap/refine/test_roadmap_refine_investigation_window.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`, and the review window tests of `tests/roadmap/stage/` whose numbers depend on the first request.
- No setting, so no ConfigMap rollout.

## Feasibility

Checked against pydantic-ai 2.59.0 (source) and runs of the real `investigate()` with a scripted `FunctionModel`. No live model call.

- The estimate is high. On three large source files read as numbered tool answers, the JSON dump counts 1.16 to 1.20 times the text of the same messages with tiktoken. The 1.4 of the issue is against the count of the provider, whose tokenizer differs from tiktoken. The ratio of the live run cannot be measured again here, because the messages of that run are not stored. The usage-based design needs no factor.
- The usage is in the messages. `ModelResponse.usage.input_tokens` is set by the provider. A streamed `FunctionModel` (the investigation always streams) estimates the usage itself, and a script cannot set it. So the tests build the messages by hand, and the other tests of the investigation run with a usage that has no input, which takes the text path.
- Refuted: the unknown tool name does not use the output retry. `ToolManager._resolve_tool` raises `ModelRetry("Unknown tool name ...")`, which counts against the retries of the tool (`CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES`, 2). `consume_output_retry` runs only for the output tool, an output validator and an empty reply. A run of `investigate()` with no tool offered and a model that calls `read_file` ends with the answer, with 0 and with 1 output retry, also after two rounds of unknown calls. A third round stops the run with "Tool <text> exceeded max retries count of 2", and the tests `test_a_call_to_a_tool_that_is_gone_gets_a_retry_and_the_run_goes_on` and `test_a_third_call_to_a_tool_that_is_gone_stops_the_run_and_it_is_no_budget_limit` already cover that. So criterion 3 cannot fail today, and no code is written for it. The loss at request 15 of the live run is the output cut of 4096 tokens (#4220).
- The window of #4220 changes other functions of the same file, so the diffs do not overlap.

## Existing Tool Considered

The usage of the last reply is in the pydantic-ai messages already, and tiktoken through `count_tokens` is the project counter. No new tool and no new library is needed. The change deletes the JSON dump from `tokens_of` and the comment that says the count errs high.

Cost, as the issue states it: about 60,000 tokens to build, no tokens to keep, about 1.5 hours.

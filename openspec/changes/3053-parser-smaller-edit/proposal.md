# Proposal

## Why

Issue #3053 asks for bounded repair before a step gives up. The first part (budgets, named stops, attempt events) merged as #3568. This change is the next part that gives value alone: the class `parser`.

Three stops (#2554, #2579 and #3318) had class `parser` (`XML syntax error ... unexpected EOF`) and cost 1.77 million input tokens. The provider cannot read a long tool call of the model, for example a file of about 100 lines in one `write_file` call. The failure is deterministic for one conversation (ollama/ollama pull request 18571). The step sends the same request again with no new text, once (`CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS`), and the resend cannot help.

## What Changes

- The resend after a `parser` failure carries one more part in its last request: a message that asks for a smaller edit (one file, or one small part of a file, in each tool call). The message is `MESSAGES.roadmap.implement_parser_smaller_edit`.
- A step asks for the smaller edit once. The next `parser` failure of the step, also after a good reply, ends the turn with no resend, and the step stops with class `parser`. The `wip:` commits of the tasks that passed their verification stay in the branch, as for any stop (#3054).
- A failure of another kind inside a stream is still sent again with the same conversation. In practice the classifier reads every resendable failure as `parser`, for the reason of such a failure holds the line that names tool call parsing as a known cause (`implement_model_call_generation`).
- `ToolCallLog.parser_failures` counts the parser failures of a step.
- The change carries a MODIFIED requirement in `roadmap-implement-step`, because the request that the model gets is observable.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: the resend after a provider failure inside a stream

## Impact

- Code: `src/devops_cli/roadmap/implement_step.py` (`_run_agent`, `_ask_smaller_edit`), `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_implement_step_parser.py` (new), `tests/roadmap/test_roadmap_implement_step.py`
- Documents: `docs/roadmap/implement.md`

## Dependencies

#3054 (keep work and resume) and #3568 (budgets and attempts) are merged.

## Workflow follow-up

The other parts of #3053 have their own issues: the strategy of each round and the name of `roadmap.implement.ladder` in a one-tier stop (#3569), the guard against a repeated failed tool call (#3570), the reset of a moved HEAD (#3575), a group that changes no file (#3576), and the repair of a failed verification command (#3577). Issue #3571 holds the same work as this change.

## Feasibility

Checked on `origin/main` 363ba6ae, on 2026-11-06.

1. The cause is upstream and stays. The ollama/ollama pull request 18571 (open, read with `devops gh api repos/ollama/ollama/pulls/18571`) says that the failure is deterministic for a given conversation, and that a long file-write call makes the model drift on its closing tags. A smaller call is the change that the model can make.
2. The code path is as the issue says. `_run_agent` resends the conversation that `_resend_after` builds, with no new text. Tests run the path with a scripted model that fails inside a stream.
3. The class is the one that the classifier gives. The reason of an in-stream 400 holds the line `implement_model_call_generation`, and the rule for `parser` matches `tool call pars`. A test holds that the stop has class `parser`.

Not verified: that a real model sends a smaller call after the message. A run on a real model costs tokens and the baseline eval runs on the host now. The three stops of the evaluation show the cost of the resend that fails.

## Existing Tool Considered

pydantic/pydantic-ai (MIT, maintained) gives `ModelRetry` for a tool or output validation error, not for a provider failure inside a stream, and it does not know the Ollama parse error. No open tool covers a smaller-edit message for a provider parse error. The project builds it: about 30,000 tokens to build, 2,000 each quarter to keep, 6,000 to fix one miss, about 2 hours. It deletes no internal code.

The change fits one pull request.

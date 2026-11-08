# Design

## Decisions

- **Give `check_proposal` an optional `trace` keyword that holds a `TraceFacts` value.**: `src/devops_cli/roadmap/stage/stage_change.py:def check_proposal` already collects every problem of a reply and is called by the job, the replay and the plan check, so one keyword reaches every caller and no reply goes back to the model from two places.
- **Build `TraceFacts` from the trace of the reply's run in `src/devops_cli/roadmap/agent_run.py`, with the tool names and the `path`, `directory` and `paths` values of each JSON argument.**: `src/devops_cli/roadmap/agent_run.py:class RunTrace` holds no paths, and a code-span path claim needs them. The value keeps the check free of the message structure of a trace and keeps its signature short.
- **Read the tool names from the registry `TOOLS` and `tool_names` of `src/devops_cli/roadmap/tools.py`.**: `src/devops_cli/roadmap/stage/stage_tools.py` already imports `HOLDER_STAGE, HOLDER_STAGE_EXTENDED, tool_names` from that module, so a new tool joins the check without a second edit and no tuple of names is copied.
- **Refuse an affirmative claim only, and let a line that negates the read pass.**: The prompt asks the model to write `not checked` for a premise that the run did not check, so a negation is the supported form and a refusal of it would refuse the text that the rule asks for.
- **Skip the comparison when the caller passes no facts, and refuse every affirmative claim when the facts are empty.**: The replay of a case with no `trace` fact and the plan check have no run, and empty facts would refuse the recorded good plans. An empty `TraceFacts` is a run with zero calls, and the issue asks for its refusal.
- **Pass the facts as a keyword input of `gate_arguments` in `src/devops_cli/roadmap/stage/stage_request.py`, and add a `trace` fact to the facts of a case in `src/devops_cli/roadmap/stage/stage_eval_cases.py`.**: `gate_arguments` holds the inputs that depend on the commit and on the reply, and the trace changes with each ask. The replay reads no git and calls no model, so the trace of a recorded run comes from the case.
- **State the rule in both `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `docs/roadmap/stage.md`.**: The model needs the rule to avoid the refusal, and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` keeps the prompt and the page in step.

## Rejected alternatives

- **Give `check_proposal` the whole `RunTrace`.**: `src/devops_cli/roadmap/agent_run.py:class RunTrace` holds `tool_calls: list[ToolCallRecord]` with the argument as cut, masked text, and no path, so the check would parse the message structure for a value that a small dataclass holds once.
- **Add a separate gate module for the trace rule.**: `check_proposal` has eight callers, among them `src/devops_cli/roadmap/stage/stage.py` and `src/devops_cli/roadmap/plan_check.py`, and a second module repeats the reply parsing of each of them.
- **Enforce the rule in the planner prompt only.**: The acceptance criteria of #3266 ask for a refusal, and a prompt rule is no gate: the two reported plans passed the checks with a false claim.
- **Add a constant tuple of tool names in `src/devops_cli/roadmap/stage/stage_tools.py`.**: `src/devops_cli/roadmap/tools.py` already holds `TOOLS: Final[dict[str, ToolEntry]]` and `def tool_names(`, and `src/devops_cli/roadmap/stage/stage_tools.py` imports `tool_names`, so a second list of names would drift from the first.
- **Refuse any occurrence of the words `read` or `ran` in `## Feasibility`.**: The prompt asks for `not checked` where the run checked nothing, and a plan that quotes a requirement or states a gap would be refused for the words that the rule asks it to write.
- **Treat a case with no `trace` fact as a run of zero calls.**: The golden set holds the recorded good plans of earlier items, and the replay would refuse each affirmative read claim in them, so a good case would fail the `paths` gate.

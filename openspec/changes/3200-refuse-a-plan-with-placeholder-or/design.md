# Design

## Decisions

- **Run the content checks in `check_proposal` as a new `content_problems` function, with `probes: Sequence[str] = ()` as a keyword parameter.**: The stage job and the replay both call `check_proposal`, so one function holds the rule and the replay proves it on the golden set.
- **Reuse `is_placeholder` of `src/devops_cli/roadmap/pull_form.py` for the placeholder rule, and add no second word list or strip rule.**: `pull_form.py` already holds the placeholder words and the strip rule for the pull request form, and two lists would drift apart.
- **Set the bound in `PLAN_FIELD_MIN_CHARS = 10`.**: It refuses the recorded short fields and keeps a short real sentence such as `No alternative.`
- **Add `builds_own: bool = False` to `StageProposal`, and apply the cost rule only when it is true.**: The gate reads a fact that the model states, and not a phrase that it happens to write.
- **Match a token count as a number with an optional `k` before `token` or `tokens`, and a time as a number before `hour`, `hours`, `minute` or `minutes`, ignoring case.**: It is the cost form that rule 3 of `AGENTS.md` asks for, and it accepts `80k tokens and 4 hours`.
- **Compare each probe line against `feasibility` as an exact substring after collapsing whitespace, and judge only when `probes` is not empty, and pass the probe lines of the item from `_request` to the `check_proposal` call of `_settle` in `stage.py`.**: The prompt already asks for the quote, and a job that read no probe has nothing to quote.
- **Refuse exactly `true`, `:` and `exit 0` as a `verify` command after stripping whitespace.**: The recorded defect is an exact command that cannot fail, and a real command can hold these words in an argument.
- **Bound `summary` to `PLAN_SUMMARY_MAX_CHARS = 47`, the bound that `roadmap_stage_change.md` already tells the model, and refuse a summary that ends with `...` in the schema, so the reply returns to the model once.**: `StageProposal.summary` already has `max_length=SUMMARY_MAX_CHARS` (60), but the title adds the lead `plan #<number> ` inside that bound, so a summary under 60 is still cut. The issue text says 40, and the prompt says 47: the constant takes the prompt value so the schema and the prompt agree. The model can correct its own text, and the job never writes a cut title.
- **Replace `textwrap.shorten` in `staging_title` and `delivery_title` with the full summary, and drop `_ELLIPSIS` from `stage_change.py`.**: A title that ends in `...` hides the summary, and the pull request form already judges a long delivery title.
- **Add `GateName.CONTENT` and a `Gate` that catches `DefectType.OTHER` and calls `content_problems`.**: `run_gates` keys by gate name, so one defect type maps to one gate and the replay reports the result.
- **Update the case-count and evaluated-pull assertions of `tests/roadmap/test_roadmap_stage_eval_cases.py` for the two new cases.**: That test asserts the number of cases and the evaluated pull numbers, so a new case changes it.

## Rejected alternatives

- **Check the content only in the stage job, before the replay.**: `stage_eval_gates.py` holds `GATES` and `replay_case`, and both call `check_proposal`. A check outside `check_proposal` would leave the replay unable to prove the rule on a recorded plan.
- **Add a second placeholder word list and strip rule to `stage_change.py`.**: `src/devops_cli/roadmap/pull_form.py` already holds `def is_placeholder(text: str) -> bool:`, so a second list would state one rule twice.
- **Infer that the plan builds its own code from words in `existing_tool`.**: The issue body records four plans that carried `x` or `todo` in that field, so a phrase match would refuse a good plan or accept a placeholder one.
- **Require a token and time cost in every `existing_tool`.**: `AGENTS.md` rule 3 asks for the cost only when the change builds its own code: `To build instead, write the cost in the issue or pull request`.
- **Keep `textwrap.shorten` and raise the bound only.**: `stage_change.py` holds `_ELLIPSIS: Final[str] = "..."` and both titles call `textwrap.shorten`, so a summary over the bound still ends in `...`.
- **Reuse the `PATHS` gate for the placeholder plans.**: `GATES` maps `GateName.PATHS` to `DefectType.MISSING_PATH` and `run_gates` keys the problems by gate name, so an `other` defect in the `paths` gate would read as a missing path.
- **Leave the recorded placeholder plans with the gate `none`.**: `PENDING_GATES` is empty and `_status` marks a defect with gate `none` as `UNJUDGED`, so the replay would prove nothing about the new gate.
- **Refuse any `verify` command that contains `true` or `exit 0`.**: `stage_change.py` accepts a `verify` of the form `uv run devops ci test tests/...`; a real command can hold such a word in an argument, and the issue names the exact commands.
- **Add a new validation library for the cross-field rules.**: `stage_change.py` already holds `check_proposal` with the spec-delta, form, path and criteria checks, so a second library would duplicate the rule set and add a dependency.

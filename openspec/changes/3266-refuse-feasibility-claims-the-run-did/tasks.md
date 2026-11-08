# Tasks

## 1. Add TraceFacts and its unit test

Reads: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/tools.py`, `tests/ai/client/test_roadmap_agent_run.py`. Changes: `src/devops_cli/roadmap/agent_run.py`, `tests/ai/client/test_roadmap_agent_run.py`.

- [ ] 1.1 In `tests/ai/client/test_roadmap_agent_run.py`, add a case that builds a `RunTrace` with a `read_file` call for `src/devops_cli/roadmap/agent_run.py` and a `search_code` call for `needle`, and asserts that `TraceFacts.of` holds the tools `read_file` and `search_code` and that path. Add a case of a zero-call trace with empty `tools` and `paths`
  - Verification: `$ uv run devops ci test tests/ai/client/test_roadmap_agent_run.py` fails on the base
- [ ] 1.2 Add the frozen dataclass `TraceFacts` with `tools: frozenset[str]` and `paths: frozenset[str]` and the class method `of(trace: RunTrace)`, which reads the tool name of each call and the `path`, `directory` and `paths` values of `json.loads(record.argument)`. A value that is no string, and an argument that is no JSON object, adds nothing. The method never raises
  - Verification: `$ uv run devops ci test tests/ai/client/test_roadmap_agent_run.py` passes

## 2. Refuse an unsupported feasibility claim in the gates

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/tools.py`, `src/devops_cli/roadmap/implement/implement.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage/stage_eval_run.py`, `src/devops_cli/roadmap/stage/stage_overlap.py`, `src/devops_cli/roadmap/stage/stage_specs.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`.

- [ ] 2.1 In `tests/roadmap/stage/test_roadmap_stage_content.py`, add a case of a zero-call trace whose feasibility says `read `src/devops_cli/roadmap/agent_run.py`` and assert one problem that names that path. Add a case whose trace read the path and assert no problem for that line, a case of a missing `search_code` call, a case of `not read` the path, and a case with no trace facts. Add a case that builds this plan's own `StageProposal` and asserts that `content_problems` returns no problem for it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` fails on the base
- [ ] 2.2 Add the gate `TRACE = "trace"` to `ProposalGate` and the keyword `trace: TraceFacts | None = None` to `check_proposal` and `check_gates`, with a line in `check_gates` for `_trace_problems(proposal, trace)`. The function returns no problem for `None`. For each sentence of `proposal.feasibility` that holds a toolbox tool name in a code span, or an affirmative read word with a code-span path, it adds one problem that names the claim. A sentence with a negation before the claim adds none. Add `trace` to the keyword inputs of `gate_arguments`, and add the message templates to `src/devops_cli/lang/en/messages.py`. The other callers keep their call with no facts, so the keyword defaults to `None`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` passes

## 3. Pass the trace of the reply's run to the gates

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`.

- [ ] 3.1 In `tests/roadmap/stage/test_roadmap_stage_gates.py`, add a case of a client that appends a `RunTrace` with a `read_file` call for `src/devops_cli/roadmap/agent_run.py`, whose reply's feasibility says `read` that path, and assert that the reply passes the gates. Add a case whose appended trace holds zero calls and assert that the item is refused with a problem that names that path
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_gates.py` fails on the base
- [ ] 3.2 In `_Planner`, read the trace of the reply's ask from `self._toolbox.traces[-1]` when the client is a `ToolboxClient`, and `None` otherwise. Pass `TraceFacts.of(trace)` from `_gated` and `_repaired` through `_settle` into `_problems`, and give it to `gate_arguments` as `trace=`. The split ask and the review add no facts, and the facts of a reply are those of the trace that the ask appended
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_gates.py` passes

## 4. Judge the trace rule in the replay

Reads: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`. Changes: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [ ] 4.1 In `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, add a case whose facts hold a `trace` of zero calls and whose plan says `read` the path `src/devops_cli/roadmap/agent_run.py`, and assert that the `paths` gate refuses it with a problem that names that path. Add a case with no `trace` fact and assert that the gate refuses nothing
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 4.2 Add `trace: TraceFact | None = None` to `CaseFacts`, with `TraceFact` holding `tools` and `paths` as tuples, and read the fact from the case file. `PlanUnderTest` gains `trace: TraceFacts | None`, which `of_case` builds from the fact and `_path_gate` passes to `check_proposal` as `trace=`. A case with no `trace` key gives `None`, so the replay skips the comparison
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes

## 5. State the rule in the prompt and the stage page

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/roadmap/stage.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/roadmap/stage.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 5.1 Add one sentence to `src/devops_cli/ai/tasks/roadmap_stage_change.md`: `Feasibility` cites only the tools and the paths that this run used, and a premise that the run did not check is written as `not checked`, never as read or ran. Add the same sentence to the `## Feasibility` rule of `docs/roadmap/stage.md`. Add the sentence to the list of shared phrases in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [ ] 5.2 Edit `docs/roadmap/stage.md` and `src/devops_cli/ai/tasks/roadmap_stage_change.md` with the sentence that the prompt-rule test reads
  - Verification: `$ uv run devops ci docs` passes

## 6. Record the reported plan as a golden-set case

Reads: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`. Changes: `tests/fixtures/roadmap_eval/stage/3205-a-plan-that-cites-a-read-its-run/case.json` (new), `tests/fixtures/roadmap_eval/stage/3205-a-plan-that-cites-a-read-its-run/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3205-a-plan-that-cites-a-read-its-run/plan.json` (new), `tests/fixtures/roadmap_eval/stage/3205-a-plan-that-cites-a-read-its-run/facts.json` (new), `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `docs/ROADMAP_WORKFLOW.md`.

- [ ] 6.1 In `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, raise the case count and the pull set for the case, and write the case folder `tests/fixtures/roadmap_eval/stage/3205-a-plan-that-cites-a-read-its-run/` with the plan text of #3205, its facts with `trace` holding no tool and no path, `NO_COMMIT` for both commits with a note, and one `false_premise` defect with the gate `paths` that names the read path. Run `uv run devops roadmap eval stage --replay` before and after the case, and state the score of the set before and after in the `## Measure the stage job` section of `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py` passes
- [ ] 6.2 Edit `docs/ROADMAP_WORKFLOW.md` with the replay score before and after the case
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: A test with a trace of zero calls shows that a Feasibility line "read `src/x.py`" is refused.
- Group 2: A test with a trace that read the path shows that the same line passes.
- Group 5: The planner prompt says to cite only what the run did, and the #3210 test passes.
- Group 6: A replay case from #3205 or #3237 is in the golden set.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

# Proposal

## Why

Issue #3257: a staged design often restates the issue and gives no reason for the chosen design, and in #3163 and #3168 the missing alternative hid a wrong premise. The stage check refuses a decision with no rejected alternative and an alternative whose evidence is only an opinion, before the implementation starts.

## What Changes

- Refuse a plan that states a decision and holds no rejected alternative, and refuse a rejected alternative whose evidence holds no path and line, no quoted command output and no number, in `content_problems` of `src/devops_cli/roadmap/stage/stage_change.py`.
- Add the messages `stage_problem_no_alternative` and `stage_problem_alternative_fact` to `src/devops_cli/lang/en/messages.py`.
- State the rule in the stage planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` and in the design rule of `openspec/config.yaml`.
- Name the rejected alternatives and the false premise finding in the stage verification prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md`.
- Add `tests/roadmap/stage/test_roadmap_stage_alternatives.py` for the refusal of a decision with no alternative, the refusal of an alternative with no fact, and the acceptance of one with a fact.
- Add the golden-set case of pull request 3168 to `tests/fixtures/roadmap_eval/stage/split.json` and raise the counts of `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` and `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.
- Carry a spec delta because the stage check, the two prompts and the golden set are behavior that a consumer observes: three capabilities gain one requirement each.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/plan-text`: A decision needs a rejected alternative with a fact, The planner prompt states the rejected alternative rule
- `roadmap-stage/verification`: The verification prompt names the rejected alternatives
- `roadmap-stage-eval`: The golden set holds a plan with no rejected alternative

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `openspec/config.yaml`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_alternatives.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/fixtures/roadmap_eval/stage/3168-a-plan-with-no-rejected-alternative/case.json`, `tests/fixtures/roadmap_eval/stage/3168-a-plan-with-no-rejected-alternative/facts.json`, `tests/fixtures/roadmap_eval/stage/3168-a-plan-with-no-rejected-alternative/issue.txt`, `tests/fixtures/roadmap_eval/stage/3168-a-plan-with-no-rejected-alternative/plan.json`, `tests/fixtures/roadmap_eval/stage/split.json`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`

## Feasibility

- The probes confirm the premise: `StageProposal` defines the field `rejected` at src/devops_cli/roadmap/stage/stage_change.py:693, and they say: The path `src/devops_cli/roadmap/stage/stage_change.py` is a file of the staging commit.
- `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` showed the content gate at `src/devops_cli/roadmap/stage/stage_change.py:1866:def content_problems(proposal: StageProposal, probes: Sequence[str] = ()) -> list[str]:`, and its last text rule at `src/devops_cli/roadmap/stage/stage_change.py:1888:problems.extend(_security_problems(proposal))`. The gate holds no rule for a rejected alternative, so a plan with a decision and an empty `rejected` list passes today: that line is the defective text that group 1 quotes.
- The security rule is the shape that the new rule copies: `src/devops_cli/roadmap/stage/stage_change.py:def _security_problems` returns one problem when a trigger matches and the plan holds no security text, and `content_problems` calls it. The new helper joins the same call list.
- The constants that the plan relies on are staged as they are read: `src/devops_cli/roadmap/stage/stage_change.py:212:_PLAN_CHECK_FILE: Final[str] = "src/devops_cli/roadmap/stage/stage_change.py"` names the file whose change needs the self-acceptance test; `src/devops_cli/roadmap/stage/stage_change.py:213:_SELF_ACCEPTANCE_MARKS: Final[tuple[str, ...]] = (` holds `StageProposal`, `content_problems` and `no problem`; `src/devops_cli/roadmap/stage/stage_change.py:221:PROMPT_RULE_TEST: Final[str] = "tests/roadmap/stage/test_roadmap_stage_prompt_rules.py"` is the test that group 2 lists and verifies; `src/devops_cli/roadmap/stage/stage_change.py:267:STAGE_EVAL_TRIGGER_PATHS: Final[tuple[str, ...]] = (` holds `src/devops_cli/roadmap/stage/stage_change.py` and `src/devops_cli/ai/tasks/roadmap_stage_change.md`; `src/devops_cli/roadmap/stage/stage_change.py:276:STAGE_EVAL_REPLAY: Final[str] = "uv run devops roadmap eval stage --replay"` gives the replay command; `src/devops_cli/roadmap/stage/stage_change.py:278:_STAGE_EVAL_SCORE_WORDS: Final[tuple[str, ...]] = ("score", "before", "after")` gives the words that group 1's task holds; `src/devops_cli/roadmap/stage/stage_change.py:280:GATE_DEFECT_PATHS: Final[tuple[str, ...]] = (` holds `src/devops_cli/roadmap/stage/stage_change.py`; and `src/devops_cli/roadmap/stage/stage_change.py:284:_FAILS_ON_BASE: Final[str] = "fails on the base"` gives the phrase that group 1's test holds.
- Group 1's test task quotes the defective text `src/devops_cli/roadmap/stage/stage_change.py:1888:problems.extend(_security_problems(proposal))` and states that the three tests fail on the base, and it builds the plan's own `StageProposal` with one decision and one rejected alternative that cites a line, and asserts that `content_problems` returns no problem for it, as `GATE_DEFECT_PATHS` and `_SELF_ACCEPTANCE_MARKS` ask.
- Group 1's implementation runs `uv run devops roadmap eval stage --replay` and states the score before and after the change, as a plan that changes `src/devops_cli/roadmap/stage/stage_change.py` and `src/devops_cli/ai/tasks/roadmap_stage_change.md` must, and the score of the prompt change is the same run.
- The message catalog gains the two messages: `src/devops_cli/roadmap/stage/stage_change.py:193:_MESSAGES_FILE: Final[str] = "src/devops_cli/lang/en/messages.py"` names the file that group 1 changes, and the two messages are `stage_problem_no_alternative` and `stage_problem_alternative_fact`.
- The seed file `src/devops_cli/roadmap/stage/stage_finding_classes.json` stays unchanged: `tests/roadmap/stage/test_roadmap_stage_findings.py:207:assert finding_classes(_plans()) == load_finding_classes()` recomputes it from the saved refused replies, so a hand entry for a new message fails that test.
- The golden set holds 59 cases and 6 good ones: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:72:assert (frozenset(reviewed), len(cases), len(good)) == (EVALUATED_PULLS, 59, 6)` and `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:73:assert len(EVALUATED_PULLS) == 53`, so group 3 raises the counts to 60 cases, 6 good ones and 54 reviewed pulls.
- The replay baseline is 82 judged defects of 319: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:56:JUDGED_BASELINE: Final[tuple[int, int]] = (82, 319)` and `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:281:assert report.judged() == JUDGED_BASELINE`, so the new case raises it to (83, 320), one judged defect and one defect.
- The content gate catches the type `other`: `src/devops_cli/roadmap/stage/stage_eval_gates.py:337:Gate(GateName.CONTENT, "#3200", DefectType.OTHER, _content_gate),`, so the new case names the gate `content` and the type `other`.
- `read_file` of `tests/fixtures/roadmap_eval/stage/split.json` showed half A with 29 case names and half B with 30, so group 3 adds the case to half A and both halves hold 30.
- `read_file` of `tests/fixtures/roadmap_eval/stage/3247-a-plan-that-changes-security-md/case.json` and of its `plan.json`, `facts.json` and `issue.txt` showed the four files of a case, the null commits with the note that the case reads no commit, and one `other` defect at the `content` gate, so the new case copies that shape.
- The dependency entry names pull request #5489 and `docs/ROADMAP_WORKFLOW.md` and does not start with `#5489:`, so `src/devops_cli/roadmap/stage/stage_change.py:def issue_dependencies` reads no issue of it; `src/devops_cli/roadmap/stage/stage_change.py:def _overlap_problems` keeps an entry that holds the number and the path. The plan reads that document and changes no line of it.
- The earlier reply claimed a read of `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` that its run did not make; this run read that file and quotes its lines above.
- The heading stays `## Rejected alternatives`: the renderer `src/devops_cli/roadmap/stage/stage_change.py:def _design_file` writes that part from `proposal.rejected`, and the new rule reads `proposal.rejected` and no rendered text. This run cites the symbol and did not read its body.
- The plan adds no field to `StageProposal` and no reply key, so the #3210 test `test_the_top_level_keys_of_the_reply_are_the_fields_of_the_proposal` in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` keeps passing; this run did not read that test, so its state is not checked here.
- `load_cases` of `src/devops_cli/roadmap/stage/stage_eval_cases.py` reads the case directory, so its test needs a checkout of the repository.
- `replay_all` needs a checkout of the repository, because it replays the loaded cases through the gates.
- `check_proposal` needs a checkout of the repository at the staged commit, because its paths gate reads the tracked files.
- `content_problems` and the new `_rejected_problems` are pure functions of the proposal: they need no checkout, no client of a service and no network.
- The plan introduces no program: each verify runs `uv run devops ci test` with `devops` and `pytest` from the runner image, the replay task runs `devops` over a checkout of the repository, no failure class is new, and the pod keeps `readOnlyRootFilesystem: true` and `runAsNonRoot: true`.

## Existing Tool Considered

OpenSpec is the open, maintained tool that validates a change and its `design.md`, and the alternatives block of the issue records it as MIT with last activity 2026-11-05; this run did not check that record. It holds no rule that a decision carries a rejected alternative with one fact, so the change builds that rule in `content_problems` of `src/devops_cli/roadmap/stage/stage_change.py` at about 60k tokens to build, keep and fix, and about one day. It deletes no internal code.

## Dependencies

- Pull request #5489 changes `docs/ROADMAP_WORKFLOW.md`, the shared path: this plan reads that document and changes no line of it, so neither comes first and the two do not conflict.

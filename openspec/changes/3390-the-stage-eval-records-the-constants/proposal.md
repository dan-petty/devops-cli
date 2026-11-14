# Proposal

## Why

The stage eval replay reads the recorded facts of a case, and the good case that the plan copies records file names and no value of a constant, so the constants check that the paths gate runs has no case in the golden set and the replay cannot show its refusal of a wrong claim (#3390).

## What Changes

- Add the case files `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/case.json`, `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/issue.txt`, `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/plan.json` and `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/facts.json`; the plan states `SUMMARY_MAX_CHARS` is 40 and the facts record 60.
- Record the defect in `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/case.json` as type `other`, gate `paths`, with the message `SUMMARY_MAX_CHARS is 60 in the staged tree, but the plan says 40.`
- Add the new case to half A of `tests/fixtures/roadmap_eval/stage/split.json`, so each case is in exactly one half and the halves hold 30 cases each.
- Add `test_the_replay_catches_the_case_of_a_wrong_constant` to `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.
- Raise the golden-set count of `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` to 60 and add a test that reads the recorded constant and the empty default.
- Move the pinned replay totals of `tests/roadmap/stage/test_roadmap_stage_eval_command.py` to 60 cases and 83 of 320 judged defects.
- Add a `--record` option to `devops roadmap eval stage` in `src/devops_cli/commands/roadmap_eval_stage.py`, with `src/devops_cli/roadmap/stage/stage_eval_record.py` writing each case's cited constants from its base commit into its facts file.
- Add `tests/roadmap/stage/test_roadmap_stage_eval_record.py` and regenerate the generated page `docs/commands/roadmap.md` for the new option.
- Document the `constants` field and its empty default in the module docstring and the `CaseFacts` docstring of `src/devops_cli/roadmap/stage/stage_eval_cases.py`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage-eval`: The golden set holds a case whose plan states a wrong constant, The recorder writes the constants of a case

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_eval_record.py`, `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`
- Documents: `docs/commands/roadmap.md`
- Tests: `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/case.json`, `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/issue.txt`, `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/plan.json`, `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/facts.json`, `tests/fixtures/roadmap_eval/stage/split.json`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`, `tests/roadmap/stage/test_roadmap_stage_eval_record.py`

## Feasibility

- `probes` names the moved paths of the issue, word for word: "The path `src/devops_cli/roadmap/stage_eval_cases.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_eval_cases.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it."
- "The path `tests/roadmap/test_roadmap_stage_eval_gates.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`."
- "The path `docs/roadmap/eval.md` is no file of the staging commit. No commit in the history deleted or renamed it."
- `list_files` of `tests/fixtures/roadmap_eval/stage` lists 59 case folders and `split.json`, which matches the 59 cases that the count test asserts.
- `read_file` of `tests/fixtures/roadmap_eval/stage/split.json` shows 29 names in half A, from `tests/fixtures/roadmap_eval/stage/split.json:10:"2116-the-scanner-executor-tests-find-the",` to `tests/fixtures/roadmap_eval/stage/split.json:38:"good-3410-the-stage-gate-proves-a-negative"`, and 30 names in half B after `tests/fixtures/roadmap_eval/stage/split.json:40:"B": [`, so one more name in half A gives 30 and 30.
- `read_file` of `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/case.json` shows issue 3410, pull 3435 and the base commit: `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/case.json:6:"base_commit": "89682e41118206c680e8d2273903d00d61ae140b",`.
- `read_file` of the same case's `facts.json` shows the tracked list and no constants entry: `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/facts.json:2:"tracked": [`, so the new case is the first of that folder to record a value.
- No tool of this run counted the recorded cases that hold a constant value, so the plan claims nothing about all of them: it adds one case and one test that read one value.
- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_cases.py` shows the field and its empty default: `src/devops_cli/roadmap/stage/stage_eval_cases.py:178:constants: tuple[tuple[str, int], ...] = ()`, and `src/devops_cli/roadmap/stage/stage_eval_cases.py:class CaseFacts` names no constant in its docstring.
- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_gates.py` shows the recorded facts reach the paths gate: `src/devops_cli/roadmap/stage/stage_eval_gates.py:145:constants=dict(case.facts.constants),`, and `src/devops_cli/roadmap/stage/stage_eval_gates.py:435:def replay_case(` judges each defect against its recorded gate and message.
- `read_file` of `src/devops_cli/roadmap/stage/stage_constants.py` shows the readers the plan reuses: `src/devops_cli/roadmap/stage/stage_constants.py:229:def staged_constants(source: Path, sha: str, names: Iterable[str]) -> dict[str, int]:` and `src/devops_cli/roadmap/stage/stage_constants.py:257:def constant_problems(texts: Iterable[str], constants: Mapping[str, int]) -> list[str]:`.
- The staged tree defines the constant at 60: `src/devops_cli/roadmap/pull_form.py:40:SUMMARY_MAX_CHARS: Final[int] = 60`, and the gate builds the message from the recorded value and the stated value at `src/devops_cli/roadmap/stage/stage_constants.py:277:problems.append(`.
- `search_code` for `candidate_names(` shows the job's own read, which the recorder copies: `src/devops_cli/roadmap/stage/stage.py:2230:constants = staged_constants(self._source, self._sha, candidate_names(plan_texts(proposal)))`.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` shows the in-memory twin of the new test: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:681:def test_the_replay_passes_recorded_constants(cases: list[StageCase]) -> None:`, which asserts the same message on the paths gate.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` shows the count that the new case raises: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:71:assert (frozenset(reviewed), len(cases), len(good)) == (EVALUATED_PULLS, 59, 6)`, inside `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:def test_the_set_holds_the_reviewed_plans_and_six_good_ones`; pull 3435 keeps `EVALUATED_PULLS` at 53, so the case count is the only number that moves.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_eval_command.py` shows the pinned totals that the new case moves: `tests/roadmap/stage/test_roadmap_stage_eval_command.py:78:assert "replay through the gates: 59 case(s), 6 good" in result.output`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py:81:assert "Defects that a gate judges: 82 of 319 (26%)." in result.output` and `tests/roadmap/stage/test_roadmap_stage_eval_command.py:100:assert report["defects"] == {"judged": 82, "known": 319}`; one caught defect gives 83 of 320, which is 26% as well.
- `tests/roadmap/stage/test_roadmap_stage_screen_eval.py` holds the split test that asserts the two halves hold every case once, so the new case's name goes into half A.
- `search_code` for `--record` gives no match, and `read_file` of `src/devops_cli/commands/roadmap_eval_stage.py` shows the options of `src/devops_cli/commands/roadmap_eval_stage.py:def eval_stage_cmd`, with no recorder: `src/devops_cli/commands/roadmap_eval_stage.py:124:replay: Annotated[bool, typer.Option("--replay", help=HELP.roadmap.eval_stage_replay)] = False,`. The plan therefore cites no command with the new option, because the option exists only after the change.
- `src/devops_cli/commands/ai_gateway.py:783:typer.Option("--apply", help="Write rendered gateway configuration to file."),` shows that a command of this tree passes a literal help text, so the new option needs no new entry in the help catalog.
- The review finding is a real defect, and this plan corrects it. `read_file` of `docs/CLI_REFERENCE.md` shows an index of the group pages, not a list of options: `docs/CLI_REFERENCE.md:3:holds the full text of each command: its usage, its arguments and its options.` So an option adds no text there.
- `read_file` of `docs/commands/roadmap.md` shows the option table that the generator writes, with one row for each option of the command: `docs/commands/roadmap.md:437:Make no model call. Run the recorded plans through the gates and report which known defects each gate catches.` The new `--record` option adds a row here, so group 4 changes this page and no other generated page.
- `search_code` for `REGENERATE_DOCUMENTS` shows the staged generator command: `src/devops_cli/roadmap/stage/stage_change.py:264:REGENERATE_DOCUMENTS: Final[str] = "uv run devops docs generate"`, and `uv run devops ci docs` compares the generated pages, so the group regenerates them with that command.
- The premise holds: the replay reads the recorded facts of a case, and the copied good case records no constant, so the constants check of the paths gate has no recorded case.
- Group 4 changes `src/devops_cli/lang/en/messages.py`, so it reads `tests/roadmap/implement/test_roadmap_implement_amend.py`, the one test that imports the messages module, and names it in its task: `openspec/specs/roadmap-stage/tests-gate/spec.md` refuses a group that changes a module and names no existing test of it.
- `src/devops_cli/roadmap/stage/stage_constants.py:def staged_constants` needs a checkout of the repository at the case's base commit, because it runs `git grep` and `git show`; it needs no client and no network.
- `src/devops_cli/roadmap/stage/stage_eval_cases.py:def load_cases` needs a checkout of the repository, because it reads each case folder; it needs no client and no network.
- `find_repo_root` needs a checkout of the repository, and no client and no network; `src/devops_cli/roadmap/stage/stage_eval_gates.py:def replay_case` reads only the recorded facts, with no checkout, no client and no network.
- The first checks against the real system: `uv run python -c "from pathlib import Path; from devops_cli.roadmap.stage.stage_constants import staged_constants; print(staged_constants(Path('.'), '89682e41118206c680e8d2273903d00d61ae140b', ['SUMMARY_MAX_CHARS']))"` must print `{'SUMMARY_MAX_CHARS': 60}` for the case base commit; then `uv run devops roadmap eval stage --replay --json` must report the new case as caught, with 60 cases and 83 of 320 judged defects; then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_record.py` must pass for the recorder; then `uv run devops ci docs` must pass on the regenerated page.
- The plan introduces no program of its own: each `verify` is `uv run devops ci test`, whose programs `uv`, `devops`, `python` and `pytest` come from the runner image, with no `NOT_IN_RUNNER` tool; the failure class is the exit code of the test row, and the pod settings that apply are `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`.
- `git` comes from the runner image for the recorder's read of the base commit; the recorder writes only the facts file of a case, which is a tracked file of the checkout, and it makes no request.
- The refine block's paths predate the move of the stage modules into the subpackage, so the plan uses the paths of the staged commit; `docs/roadmap/eval.md` does not exist, so the field is documented in the two docstrings and the generated page of the command group is regenerated.

## Existing Tool Considered

The open, maintained `syrupy` pytest snapshot plugin writes `__snapshots__` files, and it has no typed per-case facts file, no reader of a constant's value at a base commit and no replay gate, so it cannot cover the need. The change builds a recorder of about 70 lines on the existing `candidate_names`, `staged_constants` and `plan_texts` readers: about 4k tokens to build, about 1k tokens per month to keep and fix, and about 3 hours elapsed.

## Dependencies

None.

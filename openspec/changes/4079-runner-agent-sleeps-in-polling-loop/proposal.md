# Proposal

## Why

The eval gate test module replays the whole golden set six times, so a narrowed devops ci test run exceeds the five-minute budget of AGENTS.md rule 5, and the implement agent waits with shell sleep calls that spend tokens and keep the runner pod alive. The change cuts the replay to one per module, gives each case its own test item, and tells the agent that a shell call returns when its command ends (#4079).

## What Changes

- `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` computes the whole-set replay once in a module-scoped fixture and gives each case its own parametrized test item.
- `src/devops_cli/ai/tasks/roadmap_implement_step.md` says that a shell call returns when its command ends and forbids polling with sleep, time.sleep and a repeated tail.
- `tests/roadmap/implement/test_roadmap_implement_prompt.py` holds the test of the no-poll rule.
- `docs/TESTING.md` records the replay rule next to the worker choice of `devops ci test`.
- The spec deltas add the replay rule to roadmap-stage-eval and the no-poll rule to roadmap-implement-step.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage-eval`: The replay of the golden set runs once per test module
- `roadmap-implement-step`: The implement prompt forbids polling

## Impact

- Documents: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `docs/TESTING.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`

## Feasibility

- Probes confirm the two cited files: "The path `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` is a file of the staging commit." and "The path `src/devops_cli/ai/tasks/roadmap_implement_step.md` is a file of the staging commit."
- The eval gate module replays the whole case list six times, in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:def test_every_gate_still_refuses_every_known_bad_plan_it_must`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:def test_each_good_plan_passes_every_gate`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:def test_no_defect_waits_for_a_gate_once_the_gates_of_3012_to_3017_are_built`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:def test_the_counts_of_each_type_are_the_baseline_that_a_change_of_a_gate_beats`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:def test_the_replay_runs_the_check_of_the_job_so_a_spec_rule_that_refuses_all_fails_it` and `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:def test_a_rule_of_the_check_that_stops_refusing_fails_the_replay_of_its_defects`.
- The set holds 49 case directories: list_files of `tests/fixtures/roadmap_eval/stage` returned 49 entries. Each of the 49 stays and is replayed; none is removed, restricted or allowlisted, because the replay must judge every case. The refine block states 69 cases, so the plan repeats no case total.
- The count that `load_cases` returns is unverified, because no read-only tool runs it. The first group's verify runs the module, whose shape test compares the collected case items with the list that `load_cases` returns, and the group stops when the two differ.
- The narrowed run of one test module runs serially: `src/devops_cli/commands/ci.py:def _narrowed_workers` picks the worker count of a narrowed run. `src/devops_cli/config/defaults.py:469:DEFAULT_CI_TEST_SERIAL_MAX_FILES: Final[int] = 12` bounds the serial selection, and `src/devops_cli/config/defaults.py:470:DEFAULT_CI_TEST_NARROWED_WORKERS: Final[int] = 4` gives the workers above it.
- The full suite keeps its workers: `pyproject.toml:205:addopts = "-n logical --dist worksteal` and `docs/TESTING.md:158:runs serially for up to`. pytest-xdist is already a dev dependency: `pyproject.toml:99:"pytest-xdist==3.8.0",`.
- The issue says ci test runs pytest serially by default; that holds only for a narrowed run of up to 12 test modules. The full suite keeps addopts' worker count, so the plan adds no worker flag and changes no file under `src/devops_cli/commands/`.
- The harness needs no change: `src/devops_cli/roadmap/implement/implement_step.py:def _tune` gives the shell its allowed commands, its denied operators and its environment, and sets no command timeout and no polling loop, so a shell call returns one result when its command exits. `src/devops_cli/roadmap/implement/implement_step.py:550:coder = Coder[None](instructions=instructions, repo_context=False, sub_agents=False)` builds that agent.
- The issue says a shell sleep command violates the repository rules; no rule names a shell sleep. The applicable rules are the five-minute budget at `AGENTS.md:13:5. **Pass the checks.**`, the ban on a test that bounds elapsed time at `docs/TESTING.md:142:No test bounds elapsed wall-clock time from above.`, and the polling rule at `docs/SDLC.md:328:Never poll in rapid or sub-minute intervals.`
- `load_cases` needs a checkout of the repository: its argument is REPO_ROOT / CASES_DIRECTORY, and `src/devops_cli/roadmap/stage/stage_eval_cases.py:70:CASES_DIRECTORY: Final[Path] = Path("tests/fixtures/roadmap_eval/stage")` names the folder under the checkout.
- `replay_all` needs a checkout of the repository: `src/devops_cli/roadmap/stage/stage_eval_gates.py:419:table = registry if registry is not None else registry_table(Path.cwd())` reads the registry table from the working tree.
- `replay_case` needs a checkout of the repository: each case reads its staged tree from the checkout, so the shared report reads that tree once for the whole set.
- The first checks against the real system are `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_prompt.py` and `uv run devops ci docs`, one after each group.
- The prompt change carries the merge condition of `docs/ROADMAP_WORKFLOW.md:400:A change to the implement prompt`: the pull request gives the score of `devops roadmap eval implement` on the base and on the branch with one model. That command needs a client of the model gateway and a network, so a person runs it and the pull request states both totals.
- find_issues with the terms 'replay_all eval gate test' returned the open items #4113, #3343 and #3266 beside this item, and none of their titles names the eval gate test module. find_issues with the terms 'roadmap_implement_step prompt polling' returned no open item. The context lists no overlap, so the plan takes no dependency.

## Existing Tool Considered

pytest-xdist 3.8.0 covers parallel test execution. It is already a dev dependency (`pyproject.toml:99:"pytest-xdist==3.8.0",`) and addopts already runs it (`pyproject.toml:205:addopts = "-n logical --dist worksteal`). The change adds a module-scoped fixture and a parametrization in the eval gate test, and builds no runner.

## Dependencies

None.

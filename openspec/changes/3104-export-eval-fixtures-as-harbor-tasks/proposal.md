# Proposal

## Why

#3104: the eval commands score their fixtures with the project's own harness, so the numbers cannot be compared with other agents or harnesses, and each trial runs one at a time. A change to the prompt or to the shell policy needs a pass rate over many trials to show a gain or a loss. This change exports each implement fixture as a Harbor task and runs N trials of it with the Harbor command line, with the Coder harness of the Service as the agent, and records the pass rate and the cost.

## What Changes

- Add `src/devops_cli/roadmap/implement/implement_eval_harbor.py`: one function renders each of the four files of a Harbor task from a loaded fixture, and the exporter writes them into the task folder of the fixture.
- Add `src/devops_cli/roadmap/implement/implement_eval_harbor_run.py`: it builds the Harbor argv, reads one trial result per trial and writes the result file with the pass rate, the trial count and the total cost.
- Add the harbor sub-app of the roadmap eval group, with an export command and a run command, in `src/devops_cli/commands/roadmap_eval_harbor.py`, with its help and its messages.
- Add `DEFAULT_ROADMAP_EVAL_HARBOR_TIMEOUT_SECONDS` of 600 seconds to `src/devops_cli/config/defaults.py`, and its row to the limit table of `tests/roadmap/test_roadmap_limit_classes.py`.
- Pin one Harbor version in `pyproject.toml` and `uv.lock`, and hold both files to one version with a test.
- Refuse a fixture that lacks its issue text, a plan file or its test commands, with the existing `ROADMAP_EVAL_REFUSED` error that names the fixture and the field.
- Document both commands in `docs/TESTING.md`, and regenerate `docs/commands/roadmap.md` and `docs/CLI_REFERENCE.md` from the new help.
- Add the tests of the exporter, of the trial run and of the two commands, all of which answer harbor and docker through `process_fake`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-eval-implement`: One Harbor task folder for each implement fixture, The instruction holds the issue and the plan, The task configuration carries the time limit, The test script writes the reward of a trial, An incomplete fixture is refused, The trial command passes the trials, the agent and the provider to Harbor, The run records the pass rate and the cost, The Harbor version is pinned, No test starts Harbor or Docker, The testing document names both commands

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_eval_harbor.py`, `pyproject.toml`, `uv.lock`, `src/devops_cli/roadmap/implement/implement_eval_harbor_run.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/commands/roadmap_eval_harbor.py`, `src/devops_cli/commands/roadmap_eval.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/TESTING.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_eval_harbor.py`, `tests/roadmap/implement/test_roadmap_implement_eval_harbor_run.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/commands/test_roadmap_eval_harbor.py`

## Feasibility

- The probes confirm the premise of the issue word for word: ``The path `instruction.md` is no file of the staging commit. No commit in the history deleted or renamed it.``, ``The path `tests/test.sh` is no file of the staging commit. No commit in the history deleted or renamed it.`` and ``The path `task.toml` is no file of the staging commit. No commit in the history deleted or renamed it.``
- The fourth path that the issue names is there, and the probes say so: ``The path `docs/TESTING.md` is a file of the staging commit.``
- The first two findings are corrected: `feasibility` cites no command of the new sub-app, because that command does not exist at the staging commit. `src/devops_cli/commands/roadmap_eval.py:24:eval_app = new_typer(help=HELP.roadmap.eval_app, no_args_is_help=True)` registers the eval app, and `src/devops_cli/commands/roadmap_eval.py:26:eval_app.command("implement", help=HELP.roadmap.eval_implement)(implement_cmd)` shows the form that the new sub-app joins. The plan names the two new commands by their group and their options, and the real run is a person's run recorded in the pull request.
- The third, fourth and fifth findings are corrected: group 2 no longer changes `src/devops_cli/lang/en/messages.py`, because the refusal builds its message from the fixture name and the field and raises the existing error. Group 5 names `tests/config/test_setting_sources.py` in its reads. Group 6 names `tests/roadmap/implement/test_roadmap_implement_amend.py` and `tests/ai/mcp/test_ai_benchmark_mcp_tool.py` in its reads.
- The sixth finding is corrected: group 5 adds the row of `DEFAULT_ROADMAP_EVAL_HARBOR_TIMEOUT_SECONDS` to the table of `tests/roadmap/test_roadmap_limit_classes.py`, and its task names that path. The table is the one that `tests/roadmap/test_roadmap_limit_classes.py:91:LIMITS: Final[dict[str, tuple[str, str]]] = {` declares, and `tests/roadmap/test_roadmap_limit_classes.py:def test_every_numeric_limit_of_the_roadmap_jobs_has_a_class` fails on a new numeric constant with no row.
- `list_files` of `tests/fixtures/roadmap_eval/implement` listed 14 fixture folders, so the set that the issue names is 14 members. The plan exports each of the 14: no member is removed, restricted or allowlisted, and the census test of group 1 stops the group when a fixture is refused instead of dropping it.
- `read_file` of `src/devops_cli/roadmap/implement/implement_eval.py` lines 31 to 36 showed the names of a fixture: `src/devops_cli/roadmap/implement/implement_eval.py:31:CASE_FILE = "case.json"`, `src/devops_cli/roadmap/implement/implement_eval.py:32:ISSUE_FILE = "issue.md"` and `src/devops_cli/roadmap/implement/implement_eval.py:36:PLAN_FILES = (PROPOSAL_FILE, "design.md", "tasks.md")`.
- `read_file` of the same file showed the loaded fixture that the exporter takes: `src/devops_cli/roadmap/implement/implement_eval.py:105:class LoadedCase:`, whose fields are `src/devops_cli/roadmap/implement/implement_eval.py:111: body: str` and `src/devops_cli/roadmap/implement/implement_eval.py:112: plan: Mapping[str, str]`, so the instruction holds the issue body and the three plan files.
- `search_code` for the fixtures folder gave the staged value: `src/devops_cli/config/constants.py:3872:CONST_ROADMAP_EVAL_IMPLEMENT_FIXTURES: Final[str] = "tests/fixtures/roadmap_eval/implement"`.
- `search_code` for the reports folder gave the staged value and its reader: `src/devops_cli/config/constants.py:3873:CONST_ROADMAP_EVAL_IMPLEMENT_REPORTS: Final[str] = "eval/implement"` and `src/devops_cli/roadmap/implement/implement_eval_run.py:def report_directory`, which resolves that value under the data directory.
- `search_code` for the error code gave the error that a refused fixture raises: `src/devops_cli/exceptions/roadmap.py:class ImplementEvalError`, whose code is ROADMAP_EVAL_REFUSED, so the new refusal adds no error class.
- `read_spec` of `roadmap-eval-implement` gave its purpose and its 13 requirement names, and none of them holds a name that this delta adds, so the delta adds requirements and modifies none.
- `find_issues` for harbor listed `#3166 open feat(roadmap): run Harbor eval tasks on the cluster`, and the issue body defers the cluster run to it, so this change adds the run command and #3166 adds the cluster provider to it.
- Preconditions of the calls that the plan makes: `load_case` and `load_cases` of `src/devops_cli/roadmap/implement/implement_eval.py` need a checkout of the repository, which the command has when it runs in one; `run_subprocess` of `src/devops_cli/core/process.py` needs no checkout, no client and no network, because the caller names the program and its argv; the uv add harbor==<version> step of group 3 needs a network to the package index; the uv sync --frozen line of the generated Dockerfile needs a network to the package index; the real harbor run needs a Docker engine and a network to pull the task image.
- Runner capabilities of the programs that the plan introduces: harbor is NOT_IN_RUNNER and docker is NOT_IN_RUNNER, so no verify of this plan starts either program, and every test answers them through process_fake of `tests/support/fakes/process.py`; the verifies run uv from the image under readOnlyRootFilesystem: true, runAsNonRoot: true, capabilities.drop: ALL, seccompProfile: RuntimeDefault and allowPrivilegeEscalation: false.
- The failure class that the plan introduces is the existing ImplementEvalError with the code ROADMAP_EVAL_REFUSED, which the export and the trial run raise: a fixture that lacks a required file or field, and a trial with no reward or no cost, refuse the run with it. Every write of the export and of the report goes under its output folder, under the data directory or under tmp_path, so the read-only root filesystem of the pod is no obstacle.
- The first check against the real system is a person's run after the merge, on a workstation that holds the Docker engine and the pinned Harbor program: export the fixture 2747-env-keys into a folder under /tmp, list the four files of the folder, run one trial of that folder with the Docker provider, and record the argv, the pass rate and the cost in the pull request. The runner holds no docker and no harbor, so no verify of this plan starts them, and the offline verifies of groups 1, 4 and 6 prove the wiring first.
- Not checked: the flags of `harbor run` and the file and form of the reward of its task format. No tool of this run read the Harbor package and the runner holds no harbor, so each is one function or one constant of the new modules, and a correction of the pinned version changes one function and its test.
- The spike of the issue, 3 fixtures at 5 trials with Docker, is no group: the runner holds no docker and no harbor, so a person records it in the pull request and the plan builds no code that compensates for it. The cluster run waits on #3166.

## Existing Tool Considered

Harbor (harbor-framework/harbor, Apache-2.0, maintained) covers the task run: a task folder, the agent, the concurrency and the sandbox provider. It holds no exporter from this project's implement fixture format and no aggregation of the trial rewards into a pass rate and a cost, so the change builds those two parts: about 45k tokens to build and 3 hours, plus the cost to keep one exporter, one aggregator and the Harbor pin. The change deletes no internal code.

## Dependencies

- Pull request #5614 also changes docs/TESTING.md, the file that the documentation group edits, so the branch rebases on it before the documentation group runs.
- Issue #3166 adds the Kubernetes provider to the run command that this change adds under the harbor sub-app, so this change lands first and #3166 extends that run command.

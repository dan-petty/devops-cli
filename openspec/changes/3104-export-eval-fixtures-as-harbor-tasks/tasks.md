# Tasks

## 1. Export one Harbor task folder for each implement fixture

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_eval.py`, `src/devops_cli/config/constants.py`, `tests/fixtures/roadmap_eval/implement/2747-env-keys/case.json`. Changes: `src/devops_cli/roadmap/implement/implement_eval_harbor.py` (new), `tests/roadmap/implement/test_roadmap_implement_eval_harbor.py` (new).

- [ ] 1.1 `tests/roadmap/implement/test_roadmap_implement_eval_harbor.py` fails first with test_a_fixture_becomes_a_task_folder, because `src/devops_cli/roadmap/implement/implement_eval.py` holds no writer of a Harbor task folder
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_eval_harbor.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/roadmap/implement/implement_eval_harbor.py` with the four file names of a task as module constants, one function for each file (instruction_text, dockerfile_text, test_script_text, task_config_text) and export_task(case, folder, timeout_seconds), which writes the four files into the folder and returns it. The instruction holds the title and the body of the issue and the text of the three plan files of the `LoadedCase` that `src/devops_cli/roadmap/implement/implement_eval.py` loads. The Dockerfile starts from the public Python 3.14 image, adds uv, checks out the base commit of the case and runs uv sync --frozen. The test script runs each command of tests_pass and writes 1 or 0 as the reward in the file that the pinned Harbor version reads, held in one constant. The task configuration holds the name, the time limit and the container limits. Add test_each_committed_fixture_becomes_a_task_folder to `tests/roadmap/implement/test_roadmap_implement_eval_harbor.py`, which exports the 14 folders under the value of CONST_ROADMAP_EVAL_IMPLEMENT_FIXTURES and asserts four non-empty files in each; the group stops and records the refusal when a fixture is refused instead of dropping it
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_eval_harbor.py` passes

## 2. Refuse a fixture that lacks a required file or field

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_eval.py`, `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/roadmap/implement/implement_eval_harbor.py`. Changes: `src/devops_cli/roadmap/implement/implement_eval_harbor.py`, `tests/roadmap/implement/test_roadmap_implement_eval_harbor.py`.

- [ ] 2.1 `tests/roadmap/implement/test_roadmap_implement_eval_harbor.py` fails first with test_a_fixture_with_no_issue_text_is_refused, because `src/devops_cli/roadmap/implement/implement_eval_harbor.py` writes an empty instruction and raises no error
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_eval_harbor.py` fails on the base
- [ ] 2.2 Add require_text(fixture, field, text) to `src/devops_cli/roadmap/implement/implement_eval_harbor.py`, which raises the existing ImplementEvalError of `src/devops_cli/exceptions/roadmap.py` with the code ROADMAP_EVAL_REFUSED and a message that names the fixture and the field when the text is empty or holds no word. Call it for the issue body, for each of the three plan files and for the tests_pass commands of the case, before any file is written. Add test_a_fixture_with_no_issue_text_is_refused to `tests/roadmap/implement/test_roadmap_implement_eval_harbor.py`, which asserts the exit code, the error code and both names
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_eval_harbor.py` passes

## 3. Pin one Harbor version in both dependency files

Kind: other. Reads: `pyproject.toml`, `uv.lock`, `tests/roadmap/implement/test_roadmap_implement_eval_harbor.py`. Changes: `pyproject.toml`, `uv.lock`, `tests/roadmap/implement/test_roadmap_implement_eval_harbor.py`.

- [ ] 3.1 Add harbor==<version> to the dependencies of `pyproject.toml` with uv add harbor==<version>, which writes the same version into `uv.lock`. The version is the newest release that the step resolves, and it is the one version of both files. When deptry reports the dependency as unused, add it to the DEP002 ignore list of [tool.deptry] in the same file, with the reason that the trial command calls the harbor program and imports nothing of it. Add test_the_dependency_files_name_one_harbor_version to `tests/roadmap/implement/test_roadmap_implement_eval_harbor.py`: it reads the exact requirement of harbor from `pyproject.toml` and the version of harbor from `uv.lock` and asserts that both strings are equal
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_eval_harbor.py` passes

## 4. Build the Harbor argv, read the trials and write the result file

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_eval_harbor.py`, `src/devops_cli/roadmap/implement/implement_eval_run.py`, `src/devops_cli/core/process.py`, `tests/support/fakes/process.py`. Changes: `src/devops_cli/roadmap/implement/implement_eval_harbor_run.py` (new), `tests/roadmap/implement/test_roadmap_implement_eval_harbor_run.py` (new).

- [ ] 4.1 `tests/roadmap/implement/test_roadmap_implement_eval_harbor_run.py` fails first with test_five_trials_of_one_task and test_four_trials_three_of_them_pass, because `src/devops_cli/roadmap/implement/implement_eval_harbor.py` holds no builder of the Harbor argv and no reader of a trial
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_eval_harbor_run.py` fails on the base
- [ ] 4.2 Add `src/devops_cli/roadmap/implement/implement_eval_harbor_run.py` with HARBOR_BIN, the reports folder name, and the default agent, model and provider as module constants, and harbor_argv(task, trials, agent, model, provider, out), which builds the argv of the run command of the pinned version from the flags that its help prints: the task folder, the trial count, the agent, the model, the sandbox provider and the output folder. Add HarborTrial with its reward and its cost, HarborReport with its pass rate, its trial count, its total cost and its rewards, read_trials(folder) and run_trials(task, trials, agent, model, provider, out), which starts harbor_argv through run_subprocess of `src/devops_cli/core/process.py`, reads the trials and writes result.json into the run folder of the eval/harbor folder under the data directory, as `src/devops_cli/roadmap/implement/implement_eval_run.py` places its reports. A trial with no reward or no cost refuses with ImplementEvalError. Add test_five_trials_of_one_task and test_four_trials_three_of_them_pass to `tests/roadmap/implement/test_roadmap_implement_eval_harbor_run.py`: they install process_fake from `tests/support/fakes/process.py`, assert the whole argv for a trial count of 5 with the Coder agent and the Docker provider, write four trial files under tmp_path with three rewards of 1, and assert the report and the written file
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_eval_harbor_run.py` passes

## 5. Give the default time limit a class in the limit table

Kind: other. Reads: `src/devops_cli/config/defaults.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/config/test_setting_sources.py`. Changes: `src/devops_cli/config/defaults.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [ ] 5.1 Add DEFAULT_ROADMAP_EVAL_HARBOR_TIMEOUT_SECONDS: Final[int] = 600 to `src/devops_cli/config/defaults.py`, with a comment that names the task configuration of the pinned Harbor version as its reader. Add its row to LIMITS in `tests/roadmap/test_roadmap_limit_classes.py` with the class kept and the reason that the time limit of one trial is written into the task configuration of the task, that the export option sets it for one run, and that the task format of the pinned Harbor version reads it. Keep `tests/config/test_setting_sources.py` passing, because the new constant is a default of a command option and no setting field
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py` passes

## 6. Add the harbor export and run commands

Kind: behavior. Reads: `src/devops_cli/commands/roadmap_eval.py`, `src/devops_cli/commands/roadmap_eval_implement.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement/implement_eval_harbor.py`, `src/devops_cli/roadmap/implement/implement_eval_harbor_run.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`. Changes: `src/devops_cli/commands/roadmap_eval_harbor.py` (new), `src/devops_cli/commands/roadmap_eval.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_roadmap_eval_harbor.py` (new).

- [ ] 6.1 `tests/commands/test_roadmap_eval_harbor.py` fails first with test_export_writes_a_task_folder_for_each_fixture, because `src/devops_cli/commands/roadmap_eval.py` registers no harbor sub-app
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_eval_harbor.py tests/invariants/test_dry_run_class_ratchet.py` fails on the base
- [ ] 6.2 Add `src/devops_cli/commands/roadmap_eval_harbor.py` with the sub-app harbor_app and its two commands. export takes --fixture/-F (repeatable), --fixtures, --out, --timeout defaulting to DEFAULT_ROADMAP_EVAL_HARBOR_TIMEOUT_SECONDS and --json, and writes a task folder for each chosen case. run takes --task, --trials, --agent, --model, --provider and --json, runs the trials and prints the report. Register the sub-app in `src/devops_cli/commands/roadmap_eval.py` with eval_app.add_typer(harbor_app, name="harbor", help=HELP.roadmap.eval_harbor_app). Give export the dry-run class no-external-request and run the dry-run class request-plan. Add the help entries to `src/devops_cli/lang/en/help.py` and the messages to `src/devops_cli/lang/en/messages.py`, in the shape that `src/devops_cli/commands/roadmap_eval_implement.py` uses. Import the exporter of `src/devops_cli/roadmap/implement/implement_eval_harbor.py` and the run of `src/devops_cli/roadmap/implement/implement_eval_harbor_run.py` inside the command functions, as the implement command does, so the help of the group imports no heavy module. Add test_export_writes_a_task_folder_for_each_fixture and test_five_trials_of_one_task to `tests/commands/test_roadmap_eval_harbor.py`: they drive both commands through the shared cli fixture, assert the exported files and the recorded harbor argv, and start no program
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_eval_harbor.py tests/invariants/test_dry_run_class_ratchet.py` passes

## 7. Document the export and trial commands

Kind: other. Reads: `docs/TESTING.md`, `src/devops_cli/lang/en/help.py`. Changes: `docs/TESTING.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`.

- [ ] 7.1 Add a section to `docs/TESTING.md` that names devops roadmap eval harbor export and devops roadmap eval harbor run with the trials option, the agent, the provider, the default time limit of 600 seconds, the place of the result file under the data directory, and the rule that no test starts harbor or docker. Regenerate `docs/commands/roadmap.md` and `docs/CLI_REFERENCE.md` from the help of `src/devops_cli/lang/en/help.py` with the docs generator, so both hold the two new commands
  - Verification: `$ uv run devops ci docs` passes
- [ ] 7.2 Edit `docs/TESTING.md`, and regenerate `docs/commands/roadmap.md` and `docs/CLI_REFERENCE.md` from the help of the two new commands
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

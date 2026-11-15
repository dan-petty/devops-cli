# Design

## Decisions

- **Reuse the capability roadmap-eval-implement and add its requirements there.**: Its purpose is the measure of the implement job on its fixtures, and the Harbor export and the trials measure the same job on the same fixtures.
- **Add the export command and the run command as a harbor sub-app of the roadmap eval group.**: Issue #3166 adds the cluster provider to the same trial run, so the run is one command that #3166 extends, and the export is its sibling.
- **Write the argv builder, the trial reader and the report writer in one module and one group.**: The reader and the report writer change only files that the same group creates, so a group of their own would pack nothing for the step.
- **Render each of the four task files in one function, and assert the whole text of each in its test.**: The four files are the contract with the pinned Harbor version, so a correction of that format touches one function and one test.
- **Name the default time limit DEFAULT_ROADMAP_EVAL_HARBOR_TIMEOUT_SECONDS of 600 seconds in `src/devops_cli/config/defaults.py`, with a row of the class kept in the limit table.**: A case holds no time limit, so the export command carries it as an option with a default; the table of `tests/roadmap/test_roadmap_limit_classes.py` fails on a numeric roadmap constant with no row, and the task format of the pinned Harbor version reads the limit.
- **Write the report as result.json under the eval/harbor folder of the data directory, with the folder name a module constant of the run module.**: The implement eval writes its reports under the eval folder of the data directory, so a trial run keeps its report in the same place, and a string constant of the constants module would need no row of the limit table.
- **Pass the agent and the model as options of the run command, with the Coder agent as the default agent.**: A person changes the agent without a code change, and the flags of the pinned Harbor version are read from its help when the run module is written.
- **Answer the harbor program and the Docker engine through run_subprocess and the process fake.**: ADR 0007 and docs/TESTING.md keep a test of src/ from starting a program, and docker is NOT_IN_RUNNER, so a test that started either would fail in the gate and in the runner.
- **Leave `tests/fixtures/roadmap/alternatives_census.json` and `tests/telemetry/test_library_spans.py` unchanged.**: The census replays the check of 2026-11-11 with its recorded SBOM and deps.dev answers, and the telemetry word is part of a secret phrase that a prompt test asserts never leaves; neither reads the pin of a dependency.
- **Record the Docker spike as a person's run in the pull request, with no group.**: The runner holds no docker and no harbor, so no verify of the plan can run a real trial, and a test that started one would break ADR 0007.
- **Raise the refusal from the fixture name and the field, with no new message of `src/devops_cli/lang/en/messages.py`.**: The existing ImplementEvalError carries the code ROADMAP_EVAL_REFUSED and takes its message, so the refusal names the fixture and the field and adds no text key.

## Rejected alternatives

- **Keep the project's own harness and add a loop of N trials over it.**: `src/devops_cli/roadmap/implement/implement_eval_run.py` runs one step per fixture in one process with no concurrency, which is the problem the issue states: the trials run one at a time and the numbers are not comparable with another harness.
- **Install the Coder harness in the task container as a command line.**: The harness is a Python library of this project, and the tree holds no entry point of it that a container could install, so the trial run passes the agent to the Harbor command line instead.
- **Commit the four task files of the 14 fixtures by hand.**: A fixture is a folder of a case, an issue and a plan, as `src/devops_cli/roadmap/implement/implement_eval.py:31:CASE_FILE = "case.json"` shows, so a hand-written copy would drift from the fixture that the implement eval scores.
- **Read the time limit from the case of the fixture.**: `src/devops_cli/roadmap/implement/implement_eval.py:105:class LoadedCase:` holds the case, the body, the plan and the diffs, and the model of a case forbids an extra key, so a fixture cannot carry a time limit.

## Unchanged references

- `tests/fixtures/roadmap/alternatives_census.json` (recorded census fixture): It replays the census of 2026-11-11 with its recorded SBOM and deps.dev answers, so a new dependency does not change it.
- `tests/telemetry/test_library_spans.py` (secret phrase of a prompt test): The word is part of the secret phrase that the test asserts never leaves in a span, and it names no tool.

## Security

Adding Harbor to pyproject.toml crosses the supply-chain trust boundary: a third-party package, its transitive dependencies and the container images of the task enter the build. A person confirms the exact version and its Apache-2.0 licence, and confirms that the trial command calls the harbor program through the process seam and imports nothing of it. test_the_dependency_files_name_one_harbor_version fails when the two dependency files name different versions, and the tests of the trial command fail when a real harbor or a real docker program starts.

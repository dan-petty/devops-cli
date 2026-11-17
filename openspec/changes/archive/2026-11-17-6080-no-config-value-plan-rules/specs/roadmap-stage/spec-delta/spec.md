## ADDED Requirements

### Requirement: A scenario of a changed manifest, workflow or config file names its proof command
`check_proposal` SHALL refuse a scenario of an added or modified requirement that names, in a code span, a path that a group changes or creates outside `src/` and `tests/` and that is no Markdown document, when the scenario names no command, or names only commands that run tests. A behavior test that names the path SHALL NOT satisfy the rule. A scenario whose name the base spec of the capability holds SHALL be exempt. The problem SHALL name the scenario and the path.

#### Scenario: A changed manifest with no command
- **WHEN** a group changes `k8s/devops/cronjob-runner.yaml`, and a scenario names it and names no command
- **THEN** `check_proposal` returns one problem that names the scenario and `k8s/devops/cronjob-runner.yaml` and asks for a validator command or a live check

#### Scenario: A changed workflow or root config file with no command
- **WHEN** a group changes `.github/workflows/ci.yml` or `pyproject.toml`, and a scenario names it and names no command
- **THEN** `check_proposal` returns one problem that names the path

#### Scenario: A behavior test that names the manifest
- **WHEN** a behavior group's `test` names the changed manifest, and the scenario names no command
- **THEN** `check_proposal` returns one problem that names the manifest

#### Scenario: A validator command or a live check
- **WHEN** the scenario names `uv run devops ci --check --only k8s`, `uv run devops k8s validate k8s/devops`, `uv run devops k8s searxng-check` or `kubectl get cronjob runner`
- **THEN** `check_proposal` returns no problem for the scenario

#### Scenario: A command that runs tests
- **WHEN** the only command of the scenario is `uv run devops ci test tests/test_sample.py` or `uv run pytest tests/test_sample.py`
- **THEN** `check_proposal` returns one problem that names the manifest

#### Scenario: A scenario of the base spec
- **WHEN** the base spec of the capability holds the name of the scenario
- **THEN** `check_proposal` returns no problem for the scenario

#### Scenario: A changed Markdown document
- **WHEN** a group changes `docs/TESTING.md`, and a scenario names it with no behavior test that names it
- **THEN** `check_proposal` returns the problem of a scenario that names code with no behavior test

### Requirement: The rules of the plan ask for a command proof of a manifest, a workflow or a config file
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `openspec/config.yaml` and `docs/TESTING.md` SHALL hold the phrase "names a validator command or a live check as its proof" in the rule of a manifest, a workflow or a config file.

#### Scenario: The prompt and the documents keep the phrase
- **WHEN** a test reads the stage prompt, `openspec/config.yaml` and `docs/TESTING.md`
- **THEN** each holds "names a validator command or a live check as its proof"

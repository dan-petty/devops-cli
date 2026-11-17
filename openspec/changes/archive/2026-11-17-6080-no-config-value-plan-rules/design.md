# Design

## Decisions

### A changed file is the subject of a scenario, a file that no group changes is data
The scenario check judges a manifest, a workflow or a config file only when a group of the plan changes or creates it. A plan of a stage rule writes a path such as `.github/labels.yml` as the input of a test, and the test builds that input itself (#4316). Such a path keeps the rule of code. A path that the plan changes is what the scenario states, so its proof is a command.

### A config file is a path outside `src/` and `tests/` that is no Markdown document
`src/` and `tests/` hold the code of the project, and a test checks that code. The guard of #6075 (`is_config_path`) also counts a Markdown file as a document and not as config. A root file such as `pyproject.toml` is a config file: the check compares the code span with the paths that the groups change, so a path with no folder counts too.

### A command that runs tests is no proof
`uv run devops ci test`, `uv run devops ci coverage`, `uv run devops ci fail-to-pass`, `uv run devops ci mutate` and `pytest` run tests, and a test that reads the file asserts a value of it. Every other command span of the scenario check (`uv`, `devops`, `kubectl`, `helm`, `git`, `tofu`, `openspec` and the others) is a validator or a live check.

### A base scenario is exempt
OpenSpec refuses a MODIFIED block that leaves out a base scenario, and the job copies each one back (#4310). A plan cannot drop a base scenario of the old form, so the check judges only the scenarios that the plan writes.

### No new test module in `tests/invariants/`
A plan that changes source code gets the mirror directories of that code. A plan that changes no source code has no code for a new invariant test to check, so a new module there reads a manifest or a config file. The form check refuses it in both cases. The guard of #6075 decides at the `test-tree` row of `devops ci` whether a new test elsewhere reads such a file. An edit of an existing invariant module stays allowed.

### The workflow rule goes, and no other rule replaces it
`devops ci` runs actionlint and zizmor for each workflow, and the pre-push hook runs both when a push changes a workflow. A test that reads a workflow asserts a value of a config file.

### The golden case of #2950 names a validator
The good plan `good-2950-the-alert-case-is-a-manifest-group` had the scenario "The queries of the three panels", which a test proved by reading the dashboard. The new rule refuses it. The case now names `uv run devops ci --check --only k8s` as the proof, and a note says why. The replay of the golden set gives 6 of 6 good plans and 85 of 85 known defects caught, before and after the change.

## Rejected alternatives
- **Reuse `is_config_path` of the guard of #6075.** The guard is a module of `tests/gate/`, and the code of `src/` imports nothing from `tests/`. Its list of top folders would also need a copy in `src/`, and two lists drift.
- **Refuse every scenario that names a config path, changed or not.** The replay showed that the stage scenarios of `tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py` name `.github/labels.yml` as input data of a test, and a command does not prove such a scenario.
- **Keep `tests/invariants/` for a plan that changes no source code.** That plan has no source code to test, and the folder held most of the tests that #6075 deletes.
- **Add a Renovate config validator command here.** The issue asks only for the rules. A `devops` command that runs `renovate-config-validator` is a follow-up.

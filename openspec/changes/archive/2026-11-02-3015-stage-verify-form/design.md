# Design

## Decisions

- **The rules live in a new module `stage_form.py`, which `check_proposal` calls beside the path rule.**: `check_proposal` is the one function that the job (`_settle` of `stage.py`) and the replay (`_path_gate` of `stage_eval_gates.py`) both call, so both see the new problems. A module of its own keeps `stage_change.py` small.
- **A `verify` command is valid when it is `uv run devops` or starts with `uv run devops `, or starts with `! git grep `.**: The word boundary refuses `uv run devopsx`. The negative search is the form that `docs/TESTING.md` names for a deletion, and no `devops` command replaces it.
- **A new test module is a `creates` path under `tests/` whose name is `test_*.py`.**: A fixture, a helper or a `conftest.py` is no test module and has no package to mirror. A test that already exists is not in `creates`, so it is not judged.
- **The mirror directory of a source file `src/devops_cli/<dir>/<name>.py` is `tests/<dir>`.**: This is the rule of `docs/TESTING.md`. The check collects the mirror directories of every changed source file of the whole plan, since the test of one group may test the code of another. A module at the top of the package has `tests` as its mirror.
- **A plan with no changed source file only refuses a test module directly under `tests/`.**: The plan has no package to mirror, and the model may test code that exists already.
- **The prompt and the rules give `tests/roadmap/test_feature.py`.**: It is a real mirror of `src/devops_cli/roadmap/`, and a test reads every example path of the prompt and of `openspec/config.yaml` and checks that its folder mirrors a package.
- **The replay judges the verify form only.**: The recorded plans name new test files in `changes`, not in `creates`, so only the verify rule can be replayed. The defect type stays in `PENDING_GATES`, because the other forms of the type (a verify command that cannot fail, a missing fail-to-pass run) still wait for a gate.

## Rejected alternatives

- **Allow only `uv run devops ci test` as the prefix.**: The issue names `uv run devops ci`, `uv run devops openspec` and `uv run devops docs` as valid, and a group that changes a document needs them.
- **Refuse every command that is not `uv run devops`, with no exception.**: `docs/TESTING.md` and the stage prompt name `! git grep -n <name>` for a deletion. Refusing it would leave a deletion group with no valid command, and the model would write a `process` instead of a repeatable check.
- **Refuse every flat `tests/test_x.py`.**: `src/devops_cli/` holds top-level modules, and `tests/` mirrors them, so the flat path is the mirror for those.
- **Judge the `changes` paths and not only `creates`.**: A path in `changes` that the tree lacks and no group creates is already a missing path (#3010), so a second problem would repeat it.

# Design

## Decisions

- **Pass the own change name from `StageTarget.change` as a keyword to `check_proposal`, and compare a normalized path.**: The stage job holds the folder that it writes, and the check needs no new read. A path is under the folder when `posixpath.normpath` equals `openspec/changes/<change>` or starts with that name and a `/`.
- **Scan group `changes` and the code spans of each task, and no other text.**: These are the two places that the issue names. A `reads` path under the own folder is no work that the plan does, and a `verify` path is a command argument, so the check leaves both alone.
- **A scenario names code when a code span is a path of the staged tree or a Python identifier.**: A path is the form that `StagedTree.as_path` already recognizes. An identifier is a dotted name of letters, digits and underscores, so `_loki_mode` is a function and a sentence such as `Monolithic` in a code span is a word.
- **A behavior test covers a scenario when its `test` or `verify` holds one of the scenario's code spans, compared as one normalized word.**: The test task names the function, and the verify command names the test file. A plan that covers the scenario in either place has a test that a person can run.
- **A command exception is a code span whose first word is a command of a fixed list.**: The issue names `helm template` and `git grep`. The list also holds `kubectl`, `uv`, `devops`, `tofu`, `terraform`, `gh`, `openspec`, `pytest`, `ruff` and `mypy`, so a scenario that cites a command needs no test. A fixed list keeps a sentence with a space out of the exception.
- **A quoted references answer starts at a line with the exact header of `reference_answer`, and its file lines follow in the same `feasibility` list.**: The check reads the form that the tool writes, so a plan cannot pass with a summary of the count alone. A file line is `<path>: <count> (line <n>)`, as `stage_references` writes it.
- **A file of a quoted answer is covered by a group `changes` or `creates` path, or by a decision or rejected alternative that names it.**: The issue asks for a change or a design decision. A group `changes` path is the stronger form, and a decision that leaves the file unchanged is the other.
- **Skip a path under `openspec/changes/archive/`.**: The archive holds done work that no task changes.
- **The messages name the field, the group and the path, and the model gets them back in the retry prompt.**: The stage job returns a refused reply once, so the problem text is the instruction that corrects it.
- **The replay passes `StageCase.change` to `check_proposal`, and the new case holds the three defects of the plan of PR #3278.**: The golden set then proves the three gates on the plan that a reviewer found them in.
- **The change carries three ADDED requirements in the capability `roadmap-stage`.**: The stage job's answer to a plan is observable, so the change is no test, document or refactor and the config asks for a delta.

## Rejected alternatives

- **Infer the own change folder from the issue number in the proposal or from the first group path.**: A reply names no issue in its files, and the replay has no issue number. The stage job already holds the name, and a split reply keeps it.
- **Refuse every code span that starts with `openspec/changes/`.**: A plan can change a different change folder, and #3309 plans a move of a plan path. The check refuses only the own folder.
- **Treat any code span in a scenario as code.**: A scenario that quotes `helm template` or `git grep` would then need a behavior test for a command, which is not a behavior that a test asserts. The command exception keeps that scenario valid.
- **Accept any decision that names the file, including one that says the file changes.**: A decision is a design fact, and the issue asks the check only to name the file. The group `changes` path is the stronger form, and a decision is the form for a file that the change leaves unchanged.
- **Scan the rendered `proposal.md` and `design.md` instead of the reply fields.**: The job checks the reply before it renders, and the replay has no rendered file. The check reads the fields.
- **Add a `references` field to the reply.**: The model quotes the tool answer in `feasibility`, as the prompt already asks. A new reply key needs a prompt key and a schema change, and the issue asks for a check of the quoted answer.
- **Let a cited command cover every scenario of its requirement.**: One command would hide a second scenario that names a function with no test. The check reads each scenario on its own.
- **Set `skip_specs: true`.**: `check_proposal` decides whether the stage job accepts a plan, so a consumer observes the change and `openspec/config.yaml` asks for a delta for it.

# Design

## Decisions

- **Reuse `_is_test_module` to tell a test module from another path of a command.**: It is the one definition of a test module in the module, and a second regular expression would drift from it.
- **Judge only a `verify` command that names at least one test module.**: A documentation command and a negative search prove their group by other means, and the issue limits the rule to a command that names a test.
- **Return one problem for each unnamed test module of a command.**: A command can run more than one test module, and the model needs the name of each module that is missing.
- **Judge a path against the group's own `changes`, `creates` and `reads`, and no other group's paths.**: The step of a group reads and changes only its own files, so a path of another group proves nothing about this one.
- **Put the problem text in `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`.**: Every other stage form problem takes its text from the catalog, and a test asserts the text in one place.

## Rejected alternatives

- **Match `tests/**/test_*.py` with a new regular expression inside `form_problems`.**: `src/devops_cli/roadmap/stage_form.py` already holds `_is_test_module`, which requires the `tests` prefix, the `.py` suffix and the `test_` name prefix.
- **Judge every path under `tests/` that a command names.**: `_is_test_module` keeps a fixture, a helper and a `conftest.py` out of the rule, and `tests/roadmap/test_roadmap_stage_form.py` already asserts that such a file is not judged.
- **Judge every `verify` command, including `uv run devops ci docs` and `! git grep -n <name> src/ tests/`.**: `tests/roadmap/test_roadmap_stage_form.py` lists `uv run devops ci docs` and `! git grep -n -w old_name src/ tests/` among the accepted commands.
- **Judge only the first test module of a command.**: `tests/roadmap/test_roadmap_stage_task_verification.py` shows that a `verify` command is free text, so a command can name several modules.

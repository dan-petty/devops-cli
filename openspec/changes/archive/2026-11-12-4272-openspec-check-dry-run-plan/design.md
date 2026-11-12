# Design

## Decisions

- The command handles the dry run before `check_openspec` starts, as the archive command does (#4270). It prints `plan_check()` with `render_request_plan` and starts no process. The dry-run class stays `no-external-request`.
- `plan_check` sits in `src/devops_cli/openspec/gate.py`, next to the gate that it plans. Each module that runs a command of the gate gives the arguments of that command to the real run and to the plan: `settings_args` and `LIST_ARGS` in `tool.py`, `UPDATE_ARGS` in `skills.py`, `show_args` in `overlap.py`, and `_VALIDATION_ARGS`, `_PROBE_ARGS` and `_instruction_args` in `gate.py`. So the plan cannot differ from the real run.
- Each planned request has the variables of the run as `env`, from `isolated_environment`, which also gives the variables of the real run. The configuration directory is the placeholder `<config-home>`. The `target` of a request is the directory that the command runs in: `<config-home>`, `<checkout>`, `<skills-copy>` or `<probe>`.
- The `show` command of the overlap check runs once for each active change that `openspec list --json` gives. The plan lists it one time, with `<change>` as a placeholder and a `repeat` that says so.

## Rejected alternatives

- Let `check_openspec` skip the parse of a planned output. The later checks need the change list and the regenerated skills to decide what to run and what to report. The gate would print a half result for a tree that it did not read.
- Make `read_json` return an empty value for a planned run. This hides a real empty output of the tool and changes every caller of `read_json`.
- Write the arguments of each command again in `plan_check`. Two copies can differ, and a dry run would then list a command that the real run does not run.

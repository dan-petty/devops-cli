# Design

## Decisions

- **Directory boundary for pass-through (`allow_interspersed_args=False`, `allow_extra_args=True`, `ignore_unknown_options=False`)**: Keep `<directory>` as the first positional argument with `ctx: typer.Context`. Wrapper options placed before `<directory>` are validated strictly by Click; every token after `<directory>` is collected verbatim in `ctx.args` and appended to the `tofu` command vector without adding free-text parameters to MCP schemas.
- **Remove only named colliding short aliases (`-o`, `-v`, `-p`, `-u`)**: Remove `-u` from `init`, `-v` and `-o` from `plan`, `-v` and `-p` from `apply`, `-v` from `destroy`, `-p` and `-v` from `deploy-cloud`, and `-p` from `notify-plan`. Preserve existing long wrapper options before `<directory>`.
- **Shared helper and planner for mirror verbs**: Add `build_tf_passthrough_cmd` and `plan_tf_passthrough`, plus optional `extra_args: Sequence[str] = ()` parameters on `build_tf_{init,plan,apply,destroy,output}_cmd` and `plan_tf_{init,plan,apply,destroy,output}` in `src/devops_cli/tf/tf_plans.py`. Implement `import`, `state`, `show`, and `force-unlock` in `src/devops_cli/commands/tf.py` via one shared execution helper (`_run_tf_mirror_verb`) decorated with `@dry_run_class("request-plan")`.

## Rejected alternatives

- **Enabling `ignore_unknown_options=True` anywhere**: Would silently accept typos in wrapper flags before `<directory>` instead of rejecting `-o` or unknown wrapper flags with exit code `2`.
- **Requiring an explicit `--` separator**: Unnecessary because `<directory>` already marks the command boundary and issue usage passes `devops tf plan <dir> -out=x.plan -lock=false` directly.
- **Translation shims for `-o`, `-v`, `-p`, `-u`**: Explicitly rejected because aliases still collide with OpenTofu flags before `<directory>`.
- **A generic `devops tf run` verb or typed per-verb wrappers**: Fails the mirror-verb contract (`import`, `state`, `show`, `force-unlock`) and risks further option collisions.

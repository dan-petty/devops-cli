## Why

`devops tf` declares typed short options (`-o`, `-v`, `-p`, `-u`) that collide with OpenTofu single-dash flags such as `-out=FILE` and `-var-file=FILE`, causing Click to parse `-out=x.plan` as `-o ut=x.plan`. The wrapper also lacks `import`, `state`, `show`, and `force-unlock` subcommands. Forwarding flags after `<directory>` and exposing thin pass-through verbs aligns `devops tf` with OpenTofu and ADR 0037 (Closes #5318).

## What Changes

- Set the `<directory>` positional argument as the pass-through boundary on `devops tf` mirror verbs (`init`, `plan`, `apply`, `destroy`, `output`, `validate`, `fmt`, `import`, `state`, `show`, `force-unlock`) so options before `<directory>` are parsed by the wrapper and every token after `<directory>` passes unchanged to `tofu`.
- Remove the colliding short option aliases `-o`, `-v`, `-p`, and `-u` across `devops tf` subcommands while keeping long options before `<directory>`.
- Add thin `import`, `state`, `show`, and `force-unlock` subcommands under `devops tf`, classified as `request-plan` for `--dry-run`.
- Print the complete planned `tofu` argv (including forwarded trailing arguments) and target directory on `--dry-run` with zero subprocess calls.
- Update affected knowledge-base examples, tests, `docs/commands/tf.md`, and `docs/CLI_REFERENCE.md`.

## Capabilities

### New Capabilities

- `tf-passthrough`: Directory-boundary argument pass-through, short-alias removal (`-o`, `-v`, `-p`, `-u`), zero-request `--dry-run` output, and `import`, `state`, `show`, and `force-unlock` mirror subcommands for `devops tf`.

### Modified Capabilities

- `tf-deploy-cloud`: Replace the removed `-p` short alias with `--provider` in documented examples and requirements.

## Impact

- `src/devops_cli/commands/tf.py` and `src/devops_cli/tf/tf_plans.py`
- `src/devops_cli/lang/en/help.py`
- `src/devops_cli/ai/knowledge_base/devops_cli/tasks/infrastructure_provisioning.md`
- `src/devops_cli/ai/knowledge_base/it_domains/tools/opentofu_terraform.md`
- `src/devops_cli/ai/knowledge_base/it_domains/topics/infrastructure_as_code_and_cloud_automation.md`
- `docs/commands/tf.md` and `docs/CLI_REFERENCE.md`
- `tests/commands/test_tf.py` and `tests/commands/test_tf_dry_run.py`

## Feasibility

- Typer/Click supports `context_settings={"allow_extra_args": True, "ignore_unknown_options": True}` on subcommands that accept `ctx: typer.Context`, letting Click stop wrapper option parsing at `<directory>` so trailing OpenTofu flags (`-out=`, `-var-file=`, `-auto-approve`) pass through verbatim.
- `devops_cli/tf/tf_plans.py` and `commands/tf.py` already wrap `tofu` commands with `request-plan` `--dry-run` support; adding `import`, `state`, `show`, and `force-unlock` reuses the shared runner/plan builder without new runtime dependencies.

## Existing Tool Considered

Uses the project's existing Typer/Click context argument forwarding (`allow_extra_args` / `ignore_unknown_options`) documented in ADR 0037 rather than writing a custom shell parser or adding another CLI library. Estimated build cost: ~20,000 tokens and ~1 hour.

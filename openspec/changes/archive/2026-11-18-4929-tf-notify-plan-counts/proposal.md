# Proposal: #4929

## Why

`devops tf notify-plan` counts a plan by the fixed text `2 to add` and `1 to change`, so a plan
with other counts prints `+0 ~0 -0`. When `--plan-file` names a missing path, the command prints a
fixed sample plan and exits 0, so a caller cannot see that the file is absent. Closes #4929.

## What Changes

- The command requires `--plan-file`, and Typer refuses a missing path with a non-zero exit and an
  error that names it.
- Each count comes from its own `N to <action>` segment of the plan text, so an import segment, a
  different count and a plan with no changes all report correctly.
- The fixed sample plan is removed.

## Capabilities

### Modified

- `tf-notify-plan`: the counts come from the plan file, and a missing or absent file is an error.

## Impact

A real plan reports its own adds, changes and destroys. A caller sees a missing file instead of a
sample plan. A call without `--plan-file` exits non-zero.

## Feasibility

Confirmed against the issue and the code: `tf_notify_plan` in `src/devops_cli/commands/tf.py`
sets the counts by a fixed string match and fills a sample plan when the file is absent. The
`--plan-file` option is a `Path | None` without `exists=True`, and the command exits 0.

## Existing Tool Considered

OpenTofu (`opentofu/opentofu`, MPL-2.0, maintained) is already in use, so the verdict is `in-use`.
`tofu show -json` reads a saved plan file, not the plan output text that `--plan-file` accepts, and
the command runs under `no-external-request`; it gives no adds/changes/destroys summary for this
input. Typer supplies the missing-path refusal with `exists=True`. The change adds no dependency
and costs about 1,500 tokens to build and 300 to keep.

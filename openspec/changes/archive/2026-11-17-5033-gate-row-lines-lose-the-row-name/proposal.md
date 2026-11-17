# Proposal: #5033

## Why

Each `devops ci` row line holds the row name in square brackets, but `print_muted` reads the line
as Rich markup and removes `[name]` as a style tag. No line shows the name that `--only` and
`--skip` take, so a person who reads a failed line must guess it from the title. Closes #5033.

## What Changes

- `_check_row_line` builds every row line and escapes the bracketed name with `rich.markup.escape`,
  so Rich keeps it and still renders the badge.
- The normal, skipped, timed-out, cancelled and `python_version` lines use the helper.
- Tests check the printed line, including a name that holds markup characters.

## Capabilities

### Modified

- `ci-gate-rows`: every row line shows the name that `--only` and `--skip` take.

## Impact

The output of `devops ci` now names each row. A failed line gives the name to pass to `--only`.
The badge colors stay.

## Feasibility

Confirmed against the issue and the code: `_execute_check_async` in
`src/devops_cli/commands/ci.py` and `_run_python_version_check` build the lines, and
`print_muted` reads them as Rich markup. `rich.markup.escape` is already available.

## Existing Tool Considered

Textualize/rich is already a dependency. `rich.markup.escape` supplies the escaping, and the
change adds no dependency. No other tool builds the gate's row lines.

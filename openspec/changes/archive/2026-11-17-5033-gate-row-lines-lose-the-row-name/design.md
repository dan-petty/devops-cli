# Design

## Decisions

### Escape the bracketed name, not the name

`rich.markup.escape` must see the brackets, because `escape("format")` leaves `[format]` for Rich
to consume. `_check_row_line` escapes `f"[{name}]"` and keeps the badge markup around it. The
badge still colors the line, and the literal name survives.

### One helper for every row line

The completed, skipped, timed-out, cancelled and `python_version` lines share `_check_row_line`.
A later line cannot drop the name by building its own f-string.

### Pin the printed line

A test calls `print_muted` with the helper's line and reads the captured output, so it fails
without the escaping. A second test uses a name with brackets to cover the escape itself.

## Rejected alternatives

- **`markup=False` for the whole line:** it also drops the badge colors that show pass and fail.
- **A `rich.text.Text` with styled spans:** it works, but it is more code than escaping the one
  literal segment.
- **Escape the bare name:** it leaves the brackets that Rich consumes.

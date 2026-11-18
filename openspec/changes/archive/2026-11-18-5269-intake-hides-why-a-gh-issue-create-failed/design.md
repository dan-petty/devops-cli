# Design

## Decisions
- The exit-code check stays first: `_write` returns stdout only after exit 0, and `_validate` parses
  it only after that. A failed gh call reports its stderr before any JSON parse, so the reported
  `unexpected end of JSON input` is named as gh's stderr, not as an intake parse failure.
- The message names the command through `gh_command_name`, which stops before the first field flag
  (`-f`, `-F`, `--input`, `--raw-field`). The field values carry the title, the body and the
  labels; printing them would make the error long, could expose the body, and would push gh's
  stderr past its bound.
- The stderr is labeled `stderr: <text>` and bounded, and an empty stderr reads `stderr: (empty)`,
  so the reader never mistakes it for a parse failure of intake.
- `create_issue` passes the full title in its action, and `PlacementFailure.name` uses the full
  title, so the store error and the intake summary both name what intake sent.

## Rejected alternatives
- Keep the 64-character title and add the stderr: the cut title does not show what intake sent, and
  the intake summary still hides the title.
- Show the full title and stderr but omit the command: the command distinguishes this create write
  from the store's other writes, and the issue asks for it.
- Print the whole `gh` argv, including `-f body=...`: the body can be long and may hold sensitive
  text, and the field values would push gh's stderr past its bound.
- Parse stdout first and add stderr to the JSON error: it hides the real gh failure and reports
  `unexpected end of JSON input` on empty stdout.

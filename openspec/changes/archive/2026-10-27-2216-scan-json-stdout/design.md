# Design

Each scan command resolves the output format once, before the first progress print, and prints the muted progress line only when the resolved format is table. The JSON path then writes a single JSON document to stdout with nothing ahead of it.

The gate keeps the existing `is_dry_run()` check on commands that have a dry-run flag: `resolved == CONST_OUTPUT_FORMAT_TABLE` is the only addition to that condition. `scan workflows` returns its dry-run result before the gate, so it needs only the format check. `scan aibom` has no `--json` or `--format json` payload: it writes JSON to `--output` or to stdout, and its progress line stays gated on `output_file`, the one case where a file write is announced.

## Rejected alternatives

- **Send the progress line to stderr.** `print_muted` can write to stderr, but other devops commands print muted progress to stdout, and moving only the scan progress there changes the output of every format, not only JSON. Rejected.
- **Build the JSON payload first and print the progress line after it.** The scanner runs before either output, and the progress line signals the start of the scan; printing it after the payload would mislead on long scans and reorders every command. Rejected.
- **Add a shared helper that prints progress gated on format.** Each of the seven commands resolves its own format and prints one line; a helper would take the format, the message and the target and have no second use beyond this file. Rejected.

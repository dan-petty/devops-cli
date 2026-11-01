# Design

## Decisions

- **Use a streamed SHA-256 over the database files in sorted filename order for the osv-scanner digest.**: The 36 MB database exceeds the file-size cap of a plain file hash. A streamed hash avoids loading the file into memory. Sorting by filename makes the digest deterministic across runs on the same database.
- **Use the SHA-256 of `ruff --show-settings` JSON output for the Ruff digest.**: The issue asks for the resolved configuration, not the raw file. `--show-settings` outputs the final merged configuration as JSON, which is the exact input Ruff uses for the scan.
- **Store both digests as optional string fields on the existing ToolRun record.**: The ToolRun record already lives in the SARIF run property bag (#1983). Adding a field is the minimal change. Optional keeps the record valid for tools that do not produce a digest.

## Rejected alternatives

- **Use the database's modified time combined with a digest of its index.**: The modified time is not content-addressed: a file can be rewritten with the same mtime, or the mtime can change without a content change. A streamed content hash is more robust and matches the acceptance criterion that the digest changes when the database changes.
- **Hash the raw `ruff.toml` or `pyproject.toml` file for the Ruff digest.**: The issue and the proposed design both state the digest covers the resolved configuration, not the raw file. Ruff merges defaults with the project config, so the raw file does not capture the full input.

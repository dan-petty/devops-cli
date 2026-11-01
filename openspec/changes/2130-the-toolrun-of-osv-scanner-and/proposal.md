# Proposal

## Why

Issue #2130: the ToolRun of an osv-scanner run records no digest of its advisory database, and the ToolRun of a Ruff run records no digest of the Ruff configuration it read. Without these digests, a user cannot verify which database version or configuration produced a given scan result. The 36 MB PyPI database exceeds the file-size cap of the record's digest step, so a plain file hash is not possible.

## What Changes

- The ToolRun of an osv-scanner run records a `database_digest` field: a streamed SHA-256 over the advisory database files in sorted filename order.
- The ToolRun of a Ruff run records a `config_digest` field: the SHA-256 of the JSON output of `ruff --show-settings` for the target.
- The `review-tool-runs` capability gains two requirements that pin the digest behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-tool-runs`: osv-scanner toolrun records database digest, ruff toolrun records configuration digest

## Impact

- Code: `src/devops_cli/review/scanners/osv_scanner.py`, `src/devops_cli/review/scanners/ruff.py`
- Tests: `tests/test_review_tool_runs.py`

## Feasibility

- The issue states the ToolRun records no digest today and cites #2096 for the 36 MB database and the file-size cap. The capability `review-tool-runs` exists in the spec list, confirming the ToolRun record is a defined concept.
- Python's `hashlib` supports streaming SHA-256 over file objects, so the 36 MB database can be hashed without loading it into memory. This satisfies the file-size cap constraint.
- Ruff's `--show-settings` flag outputs the resolved configuration as JSON to stdout. A test can invoke it on a fixture directory and hash the output offline.
- First checks the implementation runs against the real system: `uv run ruff --show-settings --isolated` to confirm the flag exists and outputs JSON; `uv run devops review scan --help` to confirm the scan command and its flags; `ls` of the osv-scanner database directory to confirm the file layout for the streamed hash.

## Existing Tool Considered

Python's `hashlib` (standard library) provides the streamed SHA-256. Ruff's `--show-settings` flag outputs the resolved configuration. No external library is needed. The change adds two small functions in devops-cli's own scanner adapter code and one field to the ToolRun record. The written cost is roughly 80 lines of code and tests, well within one step's budget. No internal code is deleted.

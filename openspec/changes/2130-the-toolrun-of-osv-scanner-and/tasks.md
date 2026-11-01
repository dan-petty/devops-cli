# Tasks

## 1. Add osv-scanner database digest to the ToolRun

Reads: none. Changes: `src/devops_cli/review/scanners/osv_scanner.py`, `tests/test_review_tool_runs.py`.

- [ ] 1.1 Write a test that creates two temporary directories with different file contents, calls the new `database_digest` function on each, and asserts the digests differ. Write a second test that calls the function twice on the same directory and asserts the digests are equal. The test fails because `database_digest` does not exist yet, and verify that `uv run devops ci test tests/test_review_tool_runs.py -k osv_scanner` fails on the base
- [ ] 1.2 Add a `database_digest(db_path: Path) -> str` function to the osv-scanner adapter. It lists the files under `db_path` in sorted order by relative path, opens each file in binary mode, and feeds its bytes into a single `hashlib.sha256` object in 64 KiB chunks. It returns the hex digest. Add a `database_digest: str | None` field to the ToolRun record. In the osv-scanner scan path, call `database_digest` on the database directory and store the result in the ToolRun before the SARIF export, and verify that `uv run devops ci test tests/test_review_tool_runs.py -k osv_scanner` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Add Ruff configuration digest to the ToolRun

Reads: none. Changes: `src/devops_cli/review/scanners/ruff.py`, `tests/test_review_tool_runs.py`.

- [ ] 2.1 Write a test that creates a temporary project with a `ruff.toml`, calls the new `config_digest` function, and asserts it returns a 64-character hex string. Write a second test that modifies the `ruff.toml` and calls the function again, asserting the digest differs. The test fails because `config_digest` does not exist yet, and verify that `uv run devops ci test tests/test_review_tool_runs.py -k ruff` fails on the base
- [ ] 2.2 Add a `config_digest(target: Path) -> str` function to the Ruff adapter. It runs `ruff --show-settings --isolated <target>` via `subprocess.run`, captures stdout, and returns the SHA-256 hex digest of the JSON bytes. Add a `config_digest: str | None` field to the ToolRun record. In the Ruff scan path, call `config_digest` on the target and store the result in the ToolRun before the SARIF export, and verify that `uv run devops ci test tests/test_review_tool_runs.py -k ruff` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

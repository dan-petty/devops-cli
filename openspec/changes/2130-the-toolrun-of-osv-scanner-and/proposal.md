# Proposal

## Why

Issue #2130: the ToolRun of an osv-scanner run records no digest of its advisory database, and the ToolRun of a Ruff run is said to record no digest of the Ruff configuration. The issue asks for two results:

- The ToolRun of an osv-scanner run changes when its database changes, and stays the same when it does not.
- The ToolRun of a Ruff run changes when the Ruff configuration of the target changes.

The check on `origin/main` shows that only the first result is missing. The second result exists (see Acceptance).

## What Changes

- `OsvScanner` names the `all.zip` file of each ecosystem in its offline database as ruleset files, as `TrivyScanner` names its metadata file. The `ruleset_digest` of the ToolRun then follows the content of the database.
- The record digests a ruleset file below a read-only bind of the request (the data directory of the tool) as a stream, whatever its size. A file that is not below a bind, and every config file, keep the 50 MiB limit. `file_digest` in `src/devops_cli/ai/run_store.py` reads a file as a stream, with the same result.
- `docs/SELF_IMPROVEMENT.md` says what the osv-scanner ruleset digest covers.
- Ruff gets no change: its `config_digest` already follows the config files.
- The change has a spec delta in `review-tool-runs`: the ToolRun record in `review.md` and in the SARIF export is observable.
- The change fits one pull request.

## Acceptance

- Criterion 1, the osv-scanner digest follows the database: group 1 lets the record digest a large database file, and group 2 names the database files in the request.
- Criterion 2, the Ruff digest follows the Ruff configuration: already met on `main`. `RuffScanner.config_names` lists `.ruff.toml`, `ruff.toml` and `pyproject.toml`, and the test `test_a_changed_config_file_of_the_tree_changes_the_config_digest` pins it. Group 3 runs that test again and writes the one gap into the document: a Ruff config that uses `extend` has a base file that the digest does not cover. No criterion asks for that file, so the plan adds no code for it.

## Feasibility

All commands ran on 2026-11-01 on `origin/main`.

- The osv-scanner record has no database digest today. `git grep -n ruleset_files -- src/devops_cli/security/osv_scanner.py` prints nothing, so `OsvScanner` keeps the default hook of `BaseSecurityScanner` (`ruleset_files` returns no file). `docs/SELF_IMPROVEMENT.md` says the same: "none: the database has no metadata file yet".
- The database is one file. `OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY=<scratch> osv-scanner scan source --offline --offline-vulnerabilities --download-offline-databases --lockfile uv.lock` (osv-scanner 2.6.0, a `uv.lock` that has one PyPI package) wrote `find <scratch> -type f` = `osv-scalibr/PyPI/all.zip`, 37604846 bytes. There is no index or metadata file next to it.
- The size claim of the issue is half right. The limit of the digest step is `DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES` = 52428800 (50 MiB, `src/devops_cli/config/defaults.py`). A HEAD request for `https://osv-vulnerabilities.storage.googleapis.com/<ecosystem>/all.zip` gave `Content-Length` 37604846 for PyPI (under the limit) and 219697992 for npm (over it). Go, Maven, crates.io, RubyGems, Packagist and NuGet are between 2.6 MB and 12.7 MB.
- Naming the database file as a ruleset file today stops the scan. A scratch script built a `ToolRequest` with a sparse `all.zip` of 52428801 bytes as `ruleset_files` and called `record_tool_run`. It raised `SandboxValidationError: The file .../npm/all.zip cannot be read as a regular file of at most 52428800 bytes`. The sandbox executor builds its record with `require_files=True`, so a review with an npm database would fail. This is why group 1 comes first.
- A stream needs no memory limit. `hashlib.file_digest` (standard library, Python 3.11 and later) digested the same 52428801-byte file in 0.07 s on Python 3.14.10 (`uv run python`).
- The Ruff digest exists. `git grep -n config_names -- src/devops_cli/security/ruff.py` shows `config_names = CONST_RUFF_CONFIG_FILE_NAMES` and `config_search_upward = True`, and `record_tool_run` digests `request.config_files`. `uv run devops ci test tests/security/test_review_tool_runs.py -k "changed_config_file_of_the_tree or names_every_config_file_it_may_read"` ran 3 tests, 3 passed. The `ruff` case edits `pyproject.toml` and checks that the digest changes, and that it stays the same for an unchanged file.
- The Ruff command of the first plan does not work. `ruff --show-settings a.py` (ruff 0.16.8) printed `error: unexpected argument '--show-settings' found`. `ruff check --show-settings a.py` prints plain text, not JSON, with absolute paths (`cache_dir`, `file_resolver.project_root`), and `--isolated` ignores `ruff.toml` (`linter.line_length = 88` where the file sets 100). So a digest of that output would depend on the checkout path. The plan does not use it.
- A Ruff `extend` is not covered. With `ruff.toml` = `extend = "base.toml"` and `base.toml` = `line-length = 77`, `ruff check --show-settings a.py` printed `linter.line_length = 77`. The digest covers `ruff.toml` but not `base.toml`.
- Nothing newer did this work. `git log origin/main --since=2026-10-24 -- src/devops_cli/security/osv_scanner.py src/devops_cli/security/tool_executor.py src/devops_cli/ai/run_store.py` shows no commit about a database digest. The active changes under `openspec/changes/` that name osv-scanner or `file_digest` are this one and 2116, which adds only a test fixture requirement. An open-issue search for "osv digest" finds only #2130.
- `get_or_compute_snapshot_digest` in `src/devops_cli/security/osv_scanner.py` is not the answer. It hashes the names and modified times of `data.cache_dir/osv_db`, a directory that the scan does not read (the scan reads `osv-scalibr` below `OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY`). It feeds the `AdvisoryAnchor` of findings. `openspec/specs/config-commands/spec.md` pins it, so the plan keeps it as it is.

## Existing Tool Considered

- `hashlib.file_digest` from the Python standard library streams a file through SHA-256. No new dependency and no hand-written chunk loop.
- The record already has the right place: `BaseSecurityScanner.ruleset_files`, `ToolDataDir`, and the `ruleset_digest` of `ToolRun`. `TrivyScanner.ruleset_files` is the model for the osv-scanner hook.
- The change must keep passing: `tests/ai/test_tool_executor_contract.py::test_a_file_that_cannot_be_digested_is_refused` (a file over the limit that is not below a bind stays refused), `tests/security/test_review_tool_runs.py::test_each_review_scan_names_the_config_files_and_the_ruleset_files_its_tool_reads`, and `tests/security/test_scanner_tool_executor.py::test_a_tool_that_reads_a_fetched_database_gets_it_read_only_by_its_variable`.
- Code removed: `_is_small_regular_file` in `src/devops_cli/security/tool_executor.py` becomes a check for a regular file with an optional limit. `file_digest` no longer reads a whole file into memory.

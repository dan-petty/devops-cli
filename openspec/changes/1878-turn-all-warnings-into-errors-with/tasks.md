# Tasks

## 1. Fail on every warning and repair each warning at its source

Reads: `AGENTS.md`, `pyproject.toml`, `tests/ai/rag/test_qdrant_cluster_addressing.py`, `tests/ai/analyze/test_ai_analyze_outlines.py`, `src/devops_cli/ai/analyze/outlines.py`. Changes: `pyproject.toml`, `tests/ai/rag/test_qdrant_cluster_addressing.py`, `tests/ai/analyze/test_ai_analyze_outlines.py`.

- [ ] 1.1 Start `filterwarnings` with `"error"` at `pyproject.toml:238:filterwarnings = [` and keep the three entries that follow, each with its `#` reason on the line above. Add one `ignore` for the google-genai `_UnionGenericAlias` `DeprecationWarning`, with a comment that names Python 3.17 as its removal version. In `tests/ai/rag/test_qdrant_cluster_addressing.py`, keep the client of `create_native_qdrant_client` in a local and close it after `get_collections()`. In `test_outline_validation_and_enhancement_retries`, patch the RAG lookup that `enhance_file_metadata_with_ai` makes, as `tests/ai/analyze/test_ai_analyze_outlines.py:298:patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=mock_rag_ctx),` does in the same module. Run the census `uv run devops ci test`, repair each warning that it reports at the source in the file that raises it, and stop with the warning named when it has no source in this repository
  - Verification: `$ uv run devops ci test` passes

## 2. Check the warning filter and its reasons in the test-settings check

Reads: `pyproject.toml`, `tests/support/check_test_settings.py`, `tests/support/paths.py`, `src/devops_cli/commands/ci.py`. Changes: `tests/support/check_test_settings.py`, `tests/invariants/test_test_settings_row.py` (new).

- [ ] 2.1 Write `tests/invariants/test_test_settings_row.py` first: it copies `pyproject.toml` and `tests/conftest.py` into a `tmp_path` tree, calls `check_test_settings(tmp_path)` once for each fault, and asserts the return of 1 and the message. Then in `tests/support/check_test_settings.py:def check_test_settings`, read the source lines of `pyproject.toml` beside the parsed data. Fail when the first entry of `filterwarnings` is not `"error"`, fail when an entry after it has no `#` comment on its line or on the line above, and fail when no entry names `_UnionGenericAlias` or no comment on that entry names `Python 3.17`. Print the fault to stderr and return 1, as the existing checks do
  - Verification: `$ uv run devops ci test tests/invariants/test_test_settings_row.py` passes

## 3. Prove with pytester that a warning fails a run

Reads: `tests/config/test_isolation_tripwire.py`, `pyproject.toml`. Changes: `tests/invariants/test_warning_filters.py` (new).

- [ ] 3.1 Write `tests/invariants/test_warning_filters.py` with the module-level registration `pytest_plugins = ("pytester",)`, as `tests/config/test_isolation_tripwire.py:34:pytest_plugins = ("pytester",)` does. In `test_a_deprecation_warning_fails_the_inner_run`, read the `filterwarnings` list from `pyproject.toml` with `tomllib`, write it into a `pytest.ini` with `pytester.makeini`, write an inner test that calls `warnings.warn(..., DeprecationWarning)`, and run `pytester.runpytest()`. Assert that the inner run failed and that its report names the warning as an error
  - Verification: `$ uv run devops ci test tests/invariants/test_warning_filters.py` passes

## 4. Make the uv-check row advisory in the gate

Reads: `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_ci.py`, `tests/support/fakes/process.py`, `tests/support/ci_root.py`. Changes: `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_ci.py`.

- [ ] 4.1 Add `test_a_failed_ty_row_does_not_fail_the_gate` to `tests/commands/test_ci.py`: the process fake answers `uv check` with exit 1, and `devops ci --only uv-check --no-cache` exits 0 with the row labeled advisory
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py` fails on the base
- [ ] 4.2 Write the test first, with the fake of `tests/commands/test_ci.py:439:process_fake.answer(lambda call: True, ProcessAnswer(returncode=1, stderr="failed"))`. Add `advisory: bool = False` to `src/devops_cli/commands/ci.py:class CheckSpec` and set it on the `uv-check` row of `src/devops_cli/commands/ci.py:def get_check_specs`. Add one helper that returns the names of the advisory rows. In `src/devops_cli/commands/ci.py:def _handle_ci_results`, raise `typer.Exit(1)` only when a failed row is not advisory, and keep the cache only when every row passed. In `src/devops_cli/commands/ci.py:def _print_summary`, render the advisory label of `src/devops_cli/lang/en/messages.py` for a failed advisory row. Leave `src/devops_cli/commands/ci.py:def uv_check` unchanged, so a direct run still exits 1
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py` passes

## Criteria

- Group 1: `filterwarnings` starts with `"error"`. Each exception has a reason.
- Group 1: A full run reports 0 warnings.
- Group 4: The ty version is pinned, and the ty row is advisory.
- Group 4: `uv run devops ci` passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

# Proposal

## Why

The suite lets warnings pass: the `filterwarnings` list of `pyproject.toml` holds only three narrow entries and no bare error entry, so a `DeprecationWarning` ends a run as a pass with a warning. The gate also fails on any diagnostic of the pinned `ty`, although the owner decided on 2026-10-22 that the `uv-check` row is advisory and `mypy --strict` is the blocking type gate. #1878 closes both gaps and adds a check that fails when the warning filter goes back.

## What Changes

- `pyproject.toml:238:filterwarnings = [` becomes a list whose first entry is `"error"`, and each of the three narrow entries after it keeps a `#` reason on the line above it.
- `pyproject.toml` adds one `ignore` for the google-genai `_UnionGenericAlias` `DeprecationWarning`, with a comment that names Python 3.17 as its removal version.
- `tests/ai/rag/test_qdrant_cluster_addressing.py` keeps each client in a local and closes it, at `tests/ai/rag/test_qdrant_cluster_addressing.py:66:create_native_qdrant_client(CLUSTER_URL).get_collections()` and `tests/ai/rag/test_qdrant_cluster_addressing.py:76:create_native_qdrant_client(served.url).get_collections()`.
- `test_outline_validation_and_enhancement_retries` in `tests/ai/analyze/test_ai_analyze_outlines.py` patches the RAG lookup that opens the sqlite connection, as the module's other test already does.
- `tests/support/check_test_settings.py:def check_test_settings` fails when the filter list does not start with `"error"`, when an entry after it has no reason comment, or when the google-genai ignore names no removal version.
- `tests/invariants/test_test_settings_row.py` proves each of those three failures against a `tmp_path` root, because the row passes no root of its own.
- `tests/invariants/test_warning_filters.py` holds a `pytester` negative control that proves a test which emits a `DeprecationWarning` fails under the project filter list.
- `src/devops_cli/commands/ci.py:class CheckSpec` gains an `advisory` flag, and the `uv-check` row of `src/devops_cli/commands/ci.py:def get_check_specs` sets it.
- `src/devops_cli/commands/ci.py:def _handle_ci_results` raises `typer.Exit(1)` only for a failed row that is not advisory, and `src/devops_cli/commands/ci.py:def _print_summary` labels a failed advisory row from `src/devops_cli/lang/en/messages.py`.
- `tests/commands/test_ci.py` asserts that a failed ty diagnostic leaves the gate at exit 0, and that `devops ci uv-check` still exits 1.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-gate-rows`: The test-settings row checks the warning filter, An advisory row never fails the gate

## Impact

- Code: `pyproject.toml`, `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/ai/rag/test_qdrant_cluster_addressing.py`, `tests/ai/analyze/test_ai_analyze_outlines.py`, `tests/support/check_test_settings.py`, `tests/invariants/test_test_settings_row.py`, `tests/invariants/test_warning_filters.py`, `tests/commands/test_ci.py`

## Feasibility

- The premise of the issue is confirmed. `probes` gives "The path `pyproject.toml` is a file of the staging commit.", and the `pyproject.toml` source in the context holds `pyproject.toml:238:filterwarnings = [` with only the three narrow entries `error:Logfire API is unreachable:UserWarning`, `error::pytest.PytestUnhandledThreadExceptionWarning` and `error::pytest.PytestAssertRewriteWarning`, and no bare `error` entry.
- The premise that a ty diagnostic fails the gate is confirmed. `read_file` of `src/devops_cli/commands/ci.py` lines 836 to 842 showed the `uv-check` row with no advisory field, lines 1429 to 1455 showed `_handle_ci_results` raising `typer.Exit(1)` when any row failed, and lines 2180 to 2195 showed `uv_check` exiting 1 on its own.
- The earlier plan gave a new ty release as the reason for the advisory row. That was wrong, and this plan drops it: the dev group in the context holds `"ty==0.0.92"`, and `tests/commands/test_ci.py:375:def test_ci_uv_check_type_checks_with_the_ty_the_lockfile_pins() -> None:` fails when the pin and the lock differ. The advisory row answers the owner decision of 2026-10-22, and what the gate stops failing on is a diagnostic of the pinned ty after a source or dependency change.
- The earlier plan said that the `test-settings` row reads a root that a caller passes. That was wrong. `read_file` of `src/devops_cli/commands/ci.py` showed `src/devops_cli/commands/ci.py:739:"import sys; from tests.support.check_test_settings import main; sys.exit(main())"`, and `read_file` of `tests/support/check_test_settings.py` showed `tests/support/check_test_settings.py:57:return check_test_settings()` with no argument, so the row always reads `REPO_ROOT`.
- The earlier plan's spec scenarios told a developer to run `devops ci test-settings` on a broken tree. The new scenarios describe the check function with a test root, and `tests/invariants/test_test_settings_row.py` calls `check_test_settings(tmp_path)`, so a test asserts each one offline.
- The earlier plan left the sqlite warning with no file to change. `read_file` showed `tests/ai/analyze/test_ai_analyze_outlines.py:157:def test_outline_validation_and_enhancement_retries(tmp_path: Path) -> None:`, which calls `tests/ai/analyze/test_ai_analyze_outlines.py:220:enhanced_res = enhance_file_metadata_with_ai(`. That function makes the RAG lookup at `src/devops_cli/ai/analyze/outlines.py:107:ctx = investigate_rag_context(lookup, top_k=2)`, and the module's other test patches that lookup at `tests/ai/analyze/test_ai_analyze_outlines.py:298:patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=mock_rag_ctx),`. Group 1 changes this test and patches the lookup the same way.
- The seven test IDs of the issue body do not resolve at this commit. `probes` gives "The path `tests/test_ai_agent_guardrails.py` is no file of the staging commit. Commit f209f6c89 2026-10-23 feat(release): v0.2.39 (#1947) deleted or renamed it." and "The path `test_pydantic_ai_direct.py` is no file of the staging commit. No commit in the history deleted or renamed it."
- One warning source is confirmed in the tree. `read_file` of `tests/ai/rag/test_qdrant_cluster_addressing.py` lines 61 to 78 showed `tests/ai/rag/test_qdrant_cluster_addressing.py:66:create_native_qdrant_client(CLUSTER_URL).get_collections()` and `tests/ai/rag/test_qdrant_cluster_addressing.py:76:create_native_qdrant_client(served.url).get_collections()`, each with no close of the client that it builds.
- The count of warnings of a full run is unverified: no tool of this run starts the suite. The census command is `uv run devops ci test`, it is the `verify` of group 1, and the implementation stops when the run reports a warning that the plan did not decide.
- Each member of that set gets one decision. A warning that this repository raises is removed at its source. The google-genai `_UnionGenericAlias` `DeprecationWarning` is allowlisted with a comment that names Python 3.17 as its removal version. A warning with no decision fails the census.
- `check_test_settings` with no argument needs a checkout of the repository: its default root is `REPO_ROOT` of `tests/support/paths.py`, and the row passes no argument.
- `check_test_settings(root)` with a `tmp_path` root needs no checkout, no client and no network: it reads the `pyproject.toml` and `tests/conftest.py` that the test writes there.
- `create_native_qdrant_client` needs a client of the Qdrant service: `serving_qdrant` serves one on loopback inside the test, so no request leaves the host and no cluster is reached.
- `investigate_rag_context` needs a client of the Qdrant service and a network when no test double stands in; group 1 patches it, so the outlines test reaches no network and opens no sqlite connection.
- `_handle_ci_results` needs a checkout: `clear_ci_cache` writes under the gate root, and the test gives it the empty tree of `ci_root` under `tmp_path`. `_print_summary` needs no checkout, no client and no network.
- The plan introduces no new program. `uv run devops ci test` and `uv run devops ci test-settings` run `uv`, `devops` and `pytest`, which the runner image holds, and their failure classes are `test`, `lint`, `types` and `ci_infra`.
- `pytest` ships the `pytester` plugin, and `tests/config/test_isolation_tripwire.py:34:pytest_plugins = ("pytester",)` shows the module-level enable, so the negative control adds no dependency. Its inner run writes only under `tmp_path`, and the pod runs as non-root with a read-only root filesystem, `capabilities.drop: ALL` and `RuntimeDefault` seccomp.
- The first checks of the implementation against the real system are `uv run devops ci test-settings`, which must pass on the committed filter list, and `uv run devops ci test`, which must report zero warnings.

## Existing Tool Considered

pytest's `filterwarnings` ini option covers warnings-as-errors and its `pytester` plugin gives the negative control with no new dependency; no tool gives an advisory gate row, so the change writes one field, one helper and one branch, at about 4,000 tokens to build, about 500 tokens a year to keep and about 2,000 tokens to repair, about 30 minutes elapsed. The change deletes no code.

## Dependencies

None.

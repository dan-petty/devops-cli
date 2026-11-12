# Design

## Decisions

- **Start the `filterwarnings` list of `pyproject.toml` with `"error"` and keep the three narrow entries after it, each with its reason above it.**: pytest applies the last matching entry, so a narrow entry after `"error"` still wins for its own warning, and every other warning becomes an error.
- **Allowlist the google-genai `_UnionGenericAlias` warning with one `ignore` whose comment names Python 3.17.**: The warning comes from a private `typing` alias in a dependency, so this repository cannot remove it at its source, and the comment records when the entry goes.
- **Check the filter list in `check_test_settings`, and prove its failure paths with a test that passes a `tmp_path` root.**: The `test-settings` row calls `main()`, which calls `check_test_settings()` with no argument, so the row always reads `REPO_ROOT` and can show no broken tree; the test passes the root and shows each fault.
- **Describe the filter check in the spec as the check function with a test root, and not as a run of the row on a broken tree.**: The row passes no root, so no test can assert a scenario that runs it on a broken tree, and a scenario that no test asserts would be a claim of behavior that nothing proves.
- **Patch the RAG lookup in `test_outline_validation_and_enhancement_retries`, as `test_outline_extended_branches` already does.**: The test proves the retry loop of `enhance_file_metadata_with_ai`, not retrieval, and the lookup is what leaves the sqlite connection open; the patch keeps the subject of the test and reaches no network.
- **Give `CheckSpec` an `advisory` flag and read it where the gate decides its exit code.**: The cached `CheckResult` schema stays the same, so an entry written before the change is still readable, and one flag marks the row that the owner decision makes advisory.
- **Keep `devops ci uv-check` at exit 1 when `uv check` exits 1.**: `src/devops_cli/commands/ci.py:def uv_check` runs its own command and never reaches `_handle_ci_results`, so a developer who asks for the row by name still gets the failure and its diagnostics.
- **Change no ty version and no `[tool.ty.rules]` entry.**: The dev group holds `ty==0.0.92`, the lock resolves the same version, and the owner decision keeps the 12 ignored rules.
- **Put both new test modules in `tests/invariants/`.**: They check a setting and a check module of the project, not the code of one package of `src/`, and `tests/invariants/` is the folder for such a test.

## Rejected alternatives

- **Keep the `uv-check` row blocking and rely on the exact ty pin to keep the gate stable.**: A diagnostic of the pinned ty after a source or dependency change still fails `devops ci`, and the owner decided on 2026-10-22 that ty never fails it while `mypy --strict` stays the blocking type gate.
- **Prove the suite with `uv run pytest -W error` instead of the configured run.**: A command-line `-W` filter comes after the ini filters and wins, so it would override the reasoned google-genai `ignore` and fail on the third-party warning.
- **Add a separate advisory `ty` row and leave the `uv-check` row blocking.**: `uv check` still runs ty inside the blocking row, so the same diagnostic still fails the gate and the new row changes nothing.
- **Add a root option to `devops ci test-settings` so a broken tree can be shown through the row.**: `src/devops_cli/commands/ci.py:739:"import sys; from tests.support.check_test_settings import main; sys.exit(main())"` runs `main()`, and `tests/support/check_test_settings.py:57:return check_test_settings()` passes no root, so a new option would widen a command for a proof that the function's own test gives.
- **Leave the sqlite warning to the full-suite census with no file change.**: The warning is raised by `tests/ai/analyze/test_ai_analyze_outlines.py:def test_outline_validation_and_enhancement_retries`, which exists at this commit, so a census that may not change that file would fail the group with no remedy in the plan.
- **Repair the seven test IDs that the issue body names.**: `probes` reports that `tests/test_ai_agent_guardrails.py` was deleted or renamed and that `test_pydantic_ai_direct.py` is no file of the commit, so the warning list comes from the census run instead.

## Security

The change adds no host, no credential and no egress. It tightens the test configuration of `pyproject.toml`: every warning becomes an error, and the gate records the `uv-check` row as advisory while `mypy --strict` stays the blocking type gate. A person must confirm that the google-genai ignore names Python 3.17 as its removal version and that the ty pin stays exact. `uv run devops ci test-settings` fails if the filter stops starting with the error entry or an exception loses its reason, and `tests/commands/test_ci.py` fails if a ty diagnostic fails the gate.

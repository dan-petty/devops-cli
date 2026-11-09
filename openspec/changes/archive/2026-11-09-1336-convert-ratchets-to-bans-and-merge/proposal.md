# Proposal: #1336

## Why

Issue #1307 established that tests must double only process edges and mirror the source tree. Earlier issues #1309 and #1313 added ratchets with ceiling constants to hold counts during the migration. A ratchet at zero still has a ceiling that a future change can raise. ADR 0005 rejects exceptions with a stated reason.

This change converts ratchets to bans with no ceilings. It moves loose helper modules out of the root `tests/` directory into `tests/support/`, consolidates invariant tests into subject files, and keeps test rule definitions in `docs/TESTING.md`.

Closes #1336.

## What Changes

1. **Delete Ceiling Constants**:
   - Remove `CONST_ROOT_TESTS_CEILING` and `CONST_NON_MIRROR_TEST_CEILING` from `tests/invariants/test_source_tree.py`. Assert zero directly.

2. **Ban Loose Root Test Files**:
   - Move seven helper files from `tests/` to `tests/support/`: `cluster_secret_fakes.py`, `copilot_review_payloads.py`, `github_token_samples.py`, `keyring_isolation.py`, `llm_stream_fakes.py`, `project_board_fake.py`, and `project_reconcile_fake.py`.
   - Update import paths across all affected test files.
   - Add invariant ban in `tests/invariants/test_source_tree.py` forbidding `.py` files directly in `tests/` other than `conftest.py` and `__init__.py`.

3. **Convert Accommodations and Markers to Bans**:
   - In `tests/invariants/test_source_tree.py`, enforce bans for test accommodations in `src/`: `unittest.mock` imports, `PYTEST_CURRENT_TEST` checks, mock attribute checks, patch detection through `__module__`, and `unreachable(` markers.
   - Add seed unit tests demonstrating each ban fails when a violation exists under `tmp_path`.
   - Ensure failure messages name the offending `path:line` and the relevant section of `docs/TESTING.md`.

4. **Ban Module-Level CliRunner and Private Imports in Invariants**:
   - Add invariant ban against module-level `CliRunner(...)` bindings.
   - Remove module-level `CliRunner()` and private imports in `tests/invariants/test_dry_run_class_ratchet.py`. Introspect commands through public `app` from `devops_cli.main`.
   - Remove internal patch of `fetch_secret_data` in `tests/invariants/test_k8s_manifests.py` using `process_fake`.

5. **Consolidate Subject Invariant Files**:
   - Rename `tests/invariants/test_agents_md_claims.py` to `tests/invariants/test_agents_md.py`.
   - Add test in `test_agents_md.py` verifying `AGENTS.md` does not contain retired phrases: "tuple equality", "using mocks (`unittest.mock`, `pytest-mock`)", `tests/test_<submodule>.py`, `BaseLLMProvider`, and `__test__ = False`.
   - Verify every invariant test file in `tests/invariants/` is listed in `docs/TESTING.md`.

6. **Documentation Updates**:
   - Update `docs/TESTING.md` to state the converted rules as bans and list all subject files under `tests/invariants/`.
   - Update `AGENTS.md` testing link to reference both `docs/TESTING.md` and ADR 0005.

## Capabilities

- Invariant test suite deterministically prevents regression on layout, test accommodations, and direct test helper placement.
- Invariant tests rely exclusively on public application interfaces.

## Impact

- Zero impact on production runtime behavior; `skip_specs: true` is set.
- Cleaner `tests/` root directory containing only `conftest.py` and `__init__.py`.
- Enforces strict zero-tolerance invariant checks for future PRs.

## Feasibility

- AST checks already parse and validate source files in `tests/invariants/test_source_tree.py`.
- Moving the 7 test helpers to `tests/support/` resolves all root file layout violations.
- Public Click commands are already inspectable via `typer.main.get_command(app)`.
- All checks pass locally via `pytest`.

## Existing Tool Considered

No external tool is applicable. Custom AST-based invariant checks in pytest inspect repository-specific layout, import trees, and doc guidelines.

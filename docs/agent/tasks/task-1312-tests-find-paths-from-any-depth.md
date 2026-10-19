# Task: Tests Find the Repository Root and Fixtures from Any Depth, Import No Other Test Module, Build Test Data with Shared Builders, and devops test Maps a Change to Its Mirror Directory (#1312)

**Issue**: [#1312](https://github.com/dan-petty/devops-cli/issues/1312)
**Scope**: scope/cli, scope/ci
**Feasibility**: The plan on the issue was refined at a17b56b; PR 1 rechecked its survey at its base, a153042, with `rg -c 'Path\(__file__\)' tests` and `git grep -c 'Path(__file__)' a17b56b -- tests`. At a153042 `Path(__file__)` sits on 101 lines in 68 test modules and the root conftest, one module more than at a17b56b: `tests/test_claude_code_settings.py`, added by #1681. #983 PR 3 merged as #1682 at a153042, so the plan's held sites in `tests/test_gh_cmd.py` and `tests/test_github_projects.py` are no longer in flight and PR 1 converts them. `tests/__init__.py` makes `tests` a package, so `Path(tests.__file__)` is the test root wherever a module sits, and `uv run python -m tests.test_swallowed_failures_ratchet` gives that module `__spec__.name == "tests.test_swallowed_failures_ratchet"`, as pytest does. The checks the later PRs rest on (pytest 9.1.1's plugin registration and assertion rewriting, the syrupy 6.1.1 wheel, and the scratch project on the locked pytest and xdist) are recorded in the plan on the issue, and each PR that relies on one rechecks it at its base.

## Description

Every test module finds the repository root and its test data from one place, so a module reads the same paths at any depth. The item is delivered as five pull requests, in the order of the plan on the issue.

**`tests/support/` and the shared paths (PR 1).**

- **The package.** `tests/support/__init__.py` says what lives there; `tests/support/fakes/__init__.py` says it holds one fake per external edge, each with its contract suite. No test file lives under `tests/support/`.
- **The paths.** `tests/support/paths.py` defines `TESTS_ROOT = Path(tests.__file__).resolve().parent`, `REPO_ROOT = TESTS_ROOT.parent`, `FIXTURES = TESTS_ROOT / "fixtures"` and `GOLDEN = TESTS_ROOT / "golden"`. They are constants, not fixtures, because module-level constants and `parametrize` lists need a path at import.
- **The readers.** The 91 `Path(__file__)` sites in 63 modules are converted: each module drops its own root constant (`REPO_ROOT`, `_REPO_ROOT`, `_ROOT`, `ROOT`, `_PROJECT_ROOT` and function-local `repo_root` and `root`) and imports the shared one; a fixture or golden read becomes `FIXTURES` or `GOLDEN`. `tests/test_review_score.py`'s own `FIXTURES`, the review labels directory, is now `REVIEW_LABELS`. The four root-relative reads of test data (`tests/test_k8s.py`, `tests/test_review_rules_pack.py`, `tests/test_stack_dashboards.py`, `tests/test_review_prompt_consistency.py`) and the two working-directory reads (`tests/test_sandbox_traces.py`) read `FIXTURES`.
- **The ratchet.** `tests/test_swallowed_failures_ratchet.py` imports `tests.support.paths`, so it runs as a module. `CONST_LOWER_COMMAND` is built from `__spec__.name`, `uv run python -m tests.test_swallowed_failures_ratchet --lower`, which follows the module if it moves, and the usage line prints it.
- **Left for PR 5**, because each file is changed by a pull request in flight when PR 1 was written: `tests/conftest.py` (3 sites, PR 3 of this item); `tests/test_roadmap_config.py` (1 site, #1345 PR 1, #1683); `tests/test_roadmap_github_store.py` (1 site) and `tests/test_github_session.py` (1 site), #983 PR 5; `tests/test_k8s_argocd_apps.py` (1 site) and `tests/test_k8s_devops_stack.py` (3 sites), #1154 PR 2. PR 1 also leaves untouched, for the same pull requests, `tests/test_github_pr_monitor.py`, `tests/test_pr_cmd.py`, `tests/test_github_copilot_budget.py` and `tests/copilot_review_payloads.py` (#1683), `tests/test_roadmap_store_contract.py`, `tests/test_github_ssh.py`, `tests/github_session_fakes.py` and `tests/test_github_errors.py` (#983 PR 5) and `tests/test_k8s_agents_manifests.py` (#1154 PR 2), none of which reads `Path(__file__)` at a153042.

**PR 2, PR 3, PR 4 and PR 5.**

- `devops test run --changed` maps a change through the shared selector, and a `tests/support/` change forces a full `devops ci` run: PR 2 of #1312.
- The registration of `tests/support/` modules as plugins, and the floor's helpers leaving the root conftest: PR 3 of #1312.
- The builders, the example modules, the code other test modules borrow, and syrupy: PR 4 of #1312.
- The last path sites, the ban on `__file__` and on importing a test module, the move proof and `changelog.d/1312.md`: PR 5 of #1312, which closes the item.

## Acceptance Criteria

- [x] The shared paths are the repository root and its test data directories: `tests/test_architectural_invariants.py::test_the_support_paths_are_the_repository_root_and_its_test_data_directories` (`REPO_ROOT / "pyproject.toml"` names project `devops-cli`, `TESTS_ROOT == REPO_ROOT / "tests"`, and `FIXTURES` and `GOLDEN` are directories).
- [x] Outside `tests/support/`, `rg -n 'Path\(__file__\)' tests` prints only the 10 lines in the six files left for PR 5.
- [x] The ratchet runs as a module: `uv run python -m tests.test_swallowed_failures_ratchet` prints `Usage: uv run python -m tests.test_swallowed_failures_ratchet --lower`, exits 1 and writes nothing, and `test_ratchet_fails_when_file_under_ceiling_and_prints_lower_command` checks that the under-ceiling message holds that command.
- [x] No test outcome changes. At a153042, `uv run pytest --collect-only -q` collects 10703 tests; with PR 1 it collects 10704, the same IDs plus the new paths test. The full run under `-n 8` at a153042 gave 10692 passed, 2 failed, 1 skipped and 8 xfailed; the two failures, `tests/test_cli_startup_imports.py::test_cli_startup_import_budget_command_help[argv1]` and `[argv2]`, are #1680's 1.0 s wall-clock import budget exceeded at load average 13 and passed on a rerun at load average 3. With PR 1, under the same options: 10695 passed, 1 skipped and 8 xfailed, nothing failed, the base's outcomes plus the new test.
- Every later criterion of the plan on the issue: PRs 2 to 5 of #1312.

## Deliverables

- [x] `tests/support/__init__.py`, `tests/support/fakes/__init__.py` and `tests/support/paths.py`.
- [x] The 63 modules read the shared paths, and `tests/test_sandbox_traces.py` reads `FIXTURES`.
- [x] The ratchet's command and usage line, and `docs/agent/tasks/task-1347-swallowed-failures-ratchet.md`, which quoted the old command.
- PR 2 to PR 5: see Description.

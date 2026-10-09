# Task: Review Workflow Tests Start No Logfire Token Check (#965)

**Issue**: [#965](https://github.com/dan-petty/devops-cli/issues/965)
**Status**: Done
**Milestone**: v0.2.32
**Priority**: priority/p2-medium
**Scope**: type/bug, priority/p2-medium, scope/ci

## Description
Five `devops review` command tests started the Logfire SDK's `check_logfire_token` thread. The conftest DNS guard blocked the thread's lookup of the Logfire API, so every run printed "Logfire API is unreachable", and the leaked thread could resolve its host inside a later test that records socket calls, which made the dry-run socket-recorder test flaky.

The cause was in the tests. Each one patched `devops_cli.commands.review.load_settings` with a bare `MagicMock`, so `settings.telemetry.logfire` was truthy. `_init_logfire_if_enabled` (`commands/review.py`) then called `LogfireBridge.configure` (`telemetry/logfire.py`), which resolved a non-empty token from the mock through `get_logfire_token` and called `logfire.configure(send_to_logfire=True, token=...)`. That call starts the SDK's token-check thread.

The five tests now read the per-test config that the autouse `isolate_devops_cli_config` fixture writes, where `telemetry.logfire` keeps its default, off. Two `filterwarnings` entries in `pyproject.toml` make the warning an error. The warning is raised inside the background thread, so it reaches a test only as pytest's unhandled-thread warning; that warning is an error too, which fails the run whenever any background thread dies with an exception. Nothing under `src/` changes.

## Key Changes
- `tests/test_review.py`: `test_review_path_workflow`, `test_review_branch_workflow`, `test_review_pr_workflow` and `test_review_path_watch_mode` no longer patch `load_settings`. The three workflow tests also drop an inert `monkeypatch` of `devops_cli.core.validation.validate_service_url`, a name no review path reads, and the parameters left unused.
- `tests/test_review_stage_flags.py`: `test_review_cli_stage_flags_propagation` no longer patches `load_settings`.
- `pyproject.toml` (`[tool.pytest.ini_options]`): `filterwarnings` turns `Logfire API is unreachable` and `pytest.PytestUnhandledThreadExceptionWarning` into errors.

## Acceptance Criteria
- [x] The cause is named: the `MagicMock` settings made `_init_logfire_if_enabled` call `LogfireBridge.configure`, which read the token from the mock through `get_logfire_token` and called `logfire.configure`, starting the `check_logfire_token` thread.
- [x] A test run never configures the Logfire SDK unless a test asks for it: the `filterwarnings` entries in `pyproject.toml` fail any test that starts the token check, and `tests/test_review.py` and `tests/test_review_stage_flags.py` pass with them.
- [x] The corrected reproduction passes: `uv run pytest -p no:cacheprovider -q -n 0 tests/test_review.py tests/test_review_stage_flags.py -W "error:Logfire API is unreachable:UserWarning" -W "error::pytest.PytestUnhandledThreadExceptionWarning"`.
- [x] `uv run devops ci` passes: the pre-push gate and the PR's checks run it.

## Deliverables
- [x] The five tests read the per-test config instead of a `MagicMock` settings object.
- [x] `pyproject.toml` warning filters that keep the token check out of every test run.
- [x] `changelog.d/965.md`.
- The four other tests that patch `_init_logfire_if_enabled` alongside a `MagicMock` `load_settings` (the `--full` test in `tests/test_review.py`, two in `tests/test_review_pr_post.py`, one in `tests/test_review_path_routing.py`): moved to #1326, which migrates them to the `config` fixture.

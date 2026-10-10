# Task: devops serve --service leaves the process's logging alone until uvicorn applies its JSON config, so in-process tests keep their captured logs (#1543)

**Issue**: [#1543](https://github.com/dan-petty/devops-cli/issues/1543)
**Status**: Done
**Milestone**: v0.2.33
**Priority**: unset on the issue; it fixes a failing check of release pull request #1537 (owner, 2026-10-10: "fix release branch")
**Scope**: type/bug, scope/cli, scope/telemetry
**Feasibility**: Checked at release/v0.2.33 (5c5df79). Before calling `uvicorn.run`, `devops serve --service` called `setup_service_logging`, which cleared the root logger's handlers, installed a JSON stdout handler and gave the `devops_cli` logger its own handler with `propagate=False`. `tests/test_roadmap_run.py::test_service_wiring`, changed by #1532, runs the command in the pytest process with only `uvicorn.run` doubled, so that setup stayed for the rest of the session. On #1537 the Changed-Test Independence check (seed 281456038, run 2 of 3) then failed the two dispatcher log tests in `tests/test_fastmcp_contracts.py`, whose `caplog` saw no `devops_cli` record. uvicorn already applies a `log_config` dict and builds an app from a factory (`factory=True`, as the `--reload` path does), so the fix needs no new mechanism.

## Description

- `src/devops_cli/server/json_logs.py`: `setup_service_logging` becomes `service_log_config(log_level)`, which returns the same JSON setup as a `logging.config.dictConfig` dict with `disable_existing_loggers: False`.
- `src/devops_cli/commands/serve.py`: `serve --service` passes that dict to uvicorn as `log_config` and hands uvicorn a factory, `partial(create_service_app, ...)` with `factory=True`. uvicorn applies the logging config when it builds its `Config` and calls the factory afterwards, so the warning `create_service_app` logs for a managed repository with no webhook secret is still a JSON line on stdout.
- Running the command in process with `uvicorn.run` doubled no longer changes the process's logging.

## Acceptance Criteria

- [x] After `serve --service` runs in process with uvicorn doubled, a `devops_cli` log record still reaches `caplog` (`tests/test_server.py`); it failed before the fix.
- [x] No missing-secret warning is logged before `uvicorn.run` is called, and exactly one is logged once the factory builds the app (`tests/test_server.py::test_serve_service_mode_builds_the_app_after_the_server_applies_its_logging`); it failed against the first version of the fix.
- [x] `tests/test_roadmap_run.py::test_service_wiring` reads the app from the factory uvicorn receives.
- [x] The seeded run that failed on #1537 (`uv run pytest -n 0 -p randomly --randomly-seed=281456038` over the changed test files) passes, and so do two other seeds.
- [x] `changelog.d/1543.md` holds the entry under `### Fixed`.
- `uv run devops ci` is the pull request's gate.
- Pending a person, once v0.2.33 deploys: `kubectl -n devops logs deploy/roadmap-service -c service --since=10m` shows single-line JSON records from `devops_cli` and `uvicorn`, each once.

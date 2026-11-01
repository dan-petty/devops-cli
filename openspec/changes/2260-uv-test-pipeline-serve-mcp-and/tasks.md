# Tasks

## 1. uv lock and uv sync dry-run request plans

Reads: none. Changes: `src/devops_cli/commands/uv_cmd.py`, `tests/test_dry_run_uv.py`.

- [ ] 1.1 Write a failing test in tests/test_dry_run_uv.py that calls devops uv lock --dry-run and devops uv sync --dry-run with the process runner and HTTP clients patched to fail. Assert the output contains the PlannedRequest list with argv, stdin, env placeholders, condition, and repeat. Assert no external request was made. Assert the plan matches the calls recorded by a fake runner, and verify that `uv run pytest tests/test_dry_run_uv.py -v` fails on the base
- [ ] 1.2 In src/devops_cli/commands/uv_cmd.py, add --dry-run to the uv lock and uv sync commands. Build the PlannedRequest list from the same argument builder the real run uses. Print it with render_request_plan. Give both commands the request-plan class. Remove any echo-only preview (render_dry_run_result or @dry_run_command) if present, and verify that `uv run pytest tests/test_dry_run_uv.py -v` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. uv python-install and uv run dry-run request plans

Reads: none. Changes: `src/devops_cli/commands/uv_cmd.py`, `tests/test_dry_run_uv.py`.

- [ ] 2.1 Write a failing test in tests/test_dry_run_uv.py that calls devops uv python-install --dry-run and devops uv run --dry-run with the process runner and HTTP clients patched to fail. Assert the output contains the PlannedRequest list. For uv run, assert the plan lists the delegated argv, stdin, env, condition, and repeat. Assert no external request was made, and verify that `uv run pytest tests/test_dry_run_uv.py -v` fails on the base
- [ ] 2.2 In src/devops_cli/commands/uv_cmd.py, add --dry-run to the uv python-install and uv run commands. Build the PlannedRequest list from the same argument builder the real run uses. For uv run, the plan lists the delegated command's argv, stdin, env with placeholders, condition, and repeat. Print with render_request_plan. Give both commands the request-plan class, and verify that `uv run pytest tests/test_dry_run_uv.py -v` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. test load and test profile-memory dry-run request plans

Reads: none. Changes: `src/devops_cli/commands/test_cmd.py`, `tests/test_dry_run_test_cmd.py`.

- [ ] 3.1 Write a failing test in tests/test_dry_run_test_cmd.py that calls devops test load --dry-run and devops test profile-memory --dry-run with the process runner and HTTP clients patched to fail. Assert the output contains the PlannedRequest list with the k6 or HTTP request argv. Assert no external request was made. Assert the plan matches the calls recorded by a fake client, and verify that `uv run pytest tests/test_dry_run_test_cmd.py -v` fails on the base
- [ ] 3.2 In src/devops_cli/commands/test_cmd.py, replace the echo-only --dry-run of test load and test profile-memory with a request-plan dry run. Build the PlannedRequest list from the same argument builder the real run uses. Print with render_request_plan. Give both commands the request-plan class. Remove the echo-only preview, and verify that `uv run pytest tests/test_dry_run_test_cmd.py -v` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 4. test run and test sandbox dry-run request plans

Reads: none. Changes: `src/devops_cli/commands/test_cmd.py`, `tests/test_dry_run_test_cmd.py`.

- [ ] 4.1 Write a failing test in tests/test_dry_run_test_cmd.py that calls devops test run --dry-run and devops test sandbox --dry-run with the process runner and Docker client patched to fail. Assert the output contains the PlannedRequest list. Assert no external request was made. Assert the plan matches the calls recorded by a fake runner or Docker client, and verify that `uv run pytest tests/test_dry_run_test_cmd.py -v` fails on the base
- [ ] 4.2 In src/devops_cli/commands/test_cmd.py, replace the echo-only --dry-run of test run and test sandbox with a request-plan dry run. Build the PlannedRequest list from the same argument builder the real run uses. Print with render_request_plan. Give both commands the request-plan class. Remove the echo-only preview, and verify that `uv run pytest tests/test_dry_run_test_cmd.py -v` passes
- [ ] 4.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 5. mcp export-schemas local preview and mcp tools mark-only

Reads: none. Changes: `src/devops_cli/commands/mcp_cmd.py`, `tests/test_dry_run_mcp.py`.

- [ ] 5.1 Write a failing test in tests/test_dry_run_mcp.py. For mcp export-schemas: call devops mcp export-schemas --dry-run with the writer patched to fail. Assert the output prints the change and no file is written. For mcp tools: call devops --dry-run mcp tools with the process runner and HTTP clients patched to fail. Assert the command runs normally and returns its result, and verify that `uv run pytest tests/test_dry_run_mcp.py -v` fails on the base
- [ ] 5.2 In src/devops_cli/commands/mcp_cmd.py, add --dry-run to mcp export-schemas as a local preview: print the change, write nothing. Give it the no-external-request class. Give mcp tools the no-external-request class so devops --dry-run runs it normally, and verify that `uv run pytest tests/test_dry_run_mcp.py -v` passes
- [ ] 5.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 6. mcp serve and serve dry-run request plans

Reads: none. Changes: `src/devops_cli/commands/mcp_cmd.py`, `src/devops_cli/commands/serve_cmd.py`, `tests/test_dry_run_serve.py`.

- [ ] 6.1 Write a failing test in tests/test_dry_run_serve.py. For mcp serve: call devops mcp serve --dry-run with the process runner and HTTP clients patched to fail. Assert the output lists the bind and start requests. Assert no socket is opened. For serve: call devops serve --dry-run with the same guards. Assert the output lists the uvicorn bind and start requests. Assert no socket is opened, and verify that `uv run pytest tests/test_dry_run_serve.py -v` fails on the base
- [ ] 6.2 In src/devops_cli/commands/mcp_cmd.py, add --dry-run to mcp serve. The plan lists what the server would bind and start. In src/devops_cli/commands/serve_cmd.py, add --dry-run to serve. The plan lists the uvicorn.run bind and start requests. Print both with render_request_plan. Give both commands the request-plan class, and verify that `uv run pytest tests/test_dry_run_serve.py -v` passes
- [ ] 6.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 7. pipeline and ci fail-to-pass dry-run request plans

Reads: none. Changes: `src/devops_cli/commands/pipeline_cmd.py`, `src/devops_cli/commands/ci_cmd.py`, `tests/test_dry_run_pipeline_ci.py`.

- [ ] 7.1 Write a failing test in tests/test_dry_run_pipeline_ci.py. For pipeline: call devops pipeline --dry-run with the process runner patched to fail. Assert the output lists the delegated stage argv, stdin, env, condition, and repeat. For ci fail-to-pass: call devops ci fail-to-pass --dry-run with the process runner and git patched to fail. Assert the output lists the git worktree and pytest requests. Assert no external request was made, and verify that `uv run pytest tests/test_dry_run_pipeline_ci.py -v` fails on the base
- [ ] 7.2 In src/devops_cli/commands/pipeline_cmd.py, replace the echo-only --dry-run with a request-plan dry run. Build the PlannedRequest list from the same argument builder the real run uses. In src/devops_cli/commands/ci_cmd.py, replace the echo-only --dry-run of ci fail-to-pass with a request-plan dry run. Build the PlannedRequest list from the same argument builder. Print both with render_request_plan. Give both commands the request-plan class. Remove the echo-only previews, and verify that `uv run pytest tests/test_dry_run_pipeline_ci.py -v` passes
- [ ] 7.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 8. Remove 14 paths from dry_run_gaps.json and verify ratchet test

Reads: none. Changes: `tests/fixtures/dry_run_gaps.json`.

- [ ] 8.1 Write a failing test that asserts the 14 command paths are absent from tests/fixtures/dry_run_gaps.json. Run the existing ratchet test and confirm it passes with the 14 paths removed, and verify that `uv run pytest tests/test_roadmap_dry_runs.py -v` fails on the base
- [ ] 8.2 Remove the 14 paths from tests/fixtures/dry_run_gaps.json: ci fail-to-pass, mcp export-schemas, mcp serve, mcp tools, pipeline, serve, test load, test profile-memory, test run, test sandbox, uv lock, uv python-install, uv run, uv sync, and verify that `uv run pytest tests/test_roadmap_dry_runs.py -v` passes
- [ ] 8.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

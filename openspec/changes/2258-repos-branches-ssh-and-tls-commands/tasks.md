# Tasks

## 1. Mark-only branches: clean, jira, list

Reads: none. Changes: `src/devops_cli/commands/branches.py`, `tests/fixtures/dry_run_gaps.json`, `tests/test_branches_dry_run.py`.

- [ ] 1.1 Write a test that runs devops --dry-run branches clean, devops --dry-run branches jira, and devops --dry-run branches list with the process runner and HTTP clients patched to fail. Assert each command completes and returns its normal result. Assert the --dry-run option is not present on the command (no echo-only preview), and verify that `uv run devops ci test tests/test_branches_dry_run.py` fails on the base
- [ ] 1.2 Add the no-external-request class to branches clean, branches jira, and branches list. Remove any echo-only --dry-run option or render_dry_run_result call from these three commands. Remove the three entries (branches clean, branches jira, branches list) from tests/fixtures/dry_run_gaps.json, and verify that `uv run devops ci test tests/test_branches_dry_run.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Request-plan branches: sync, update

Reads: none. Changes: `src/devops_cli/commands/branches.py`, `tests/fixtures/dry_run_gaps.json`, `tests/test_branches_dry_run.py`.

- [ ] 2.1 Write a test that runs devops branches sync --dry-run and devops branches update --dry-run with GitPython's fetch and pull patched to raise. Assert no external request is made. Assert the output lists the ordered PlannedRequest items with argv, stdin, env, condition and repeat. Write a second test that runs the real command against a fake runner that records each call, and compares the recorded calls with the plan, and verify that `uv run devops ci test tests/test_branches_dry_run.py` fails on the base
- [ ] 2.2 Add --dry-run to branches sync and branches update. In the dry-run path, build each PlannedRequest from the same argument builder the real run uses (the fetch_all function in git/operations.py). Return the command's real result type marked as a dry run with the ordered PlannedRequest items. Print with render_request_plan. Give both commands the request-plan class. Remove any echo-only preview. Remove the two entries (branches sync, branches update) from tests/fixtures/dry_run_gaps.json, and verify that `uv run devops ci test tests/test_branches_dry_run.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Mark-only repos: list, worktrees prune, worktrees status

Reads: none. Changes: `src/devops_cli/commands/repos.py`, `tests/fixtures/dry_run_gaps.json`, `tests/test_repos_dry_run.py`.

- [ ] 3.1 Write a test that runs devops --dry-run repos list, devops --dry-run repos worktrees prune, and devops --dry-run repos worktrees status with the process runner and HTTP clients patched to fail. Assert each command completes and returns its normal result. Assert repos list has no echo-only --dry-run option, and verify that `uv run devops ci test tests/test_repos_dry_run.py` fails on the base
- [ ] 3.2 Add the no-external-request class to repos list, repos worktrees prune, and repos worktrees status. Remove the echo-only --dry-run option and render_dry_run_result call from repos list. Remove the three entries (repos list, repos worktrees prune, repos worktrees status) from tests/fixtures/dry_run_gaps.json, and verify that `uv run devops ci test tests/test_repos_dry_run.py` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 4. Request-plan repos: clone, clone-org, sync, update

Reads: none. Changes: `src/devops_cli/commands/repos.py`, `tests/fixtures/dry_run_gaps.json`, `tests/test_repos_dry_run.py`.

- [ ] 4.1 Write a test that runs devops repos clone --dry-run, devops repos clone-org --dry-run, devops repos sync --dry-run, and devops repos update --dry-run with GitPython's clone_from, fetch and pull patched to raise, and the GitHub session patched to raise. Assert no external request is made. Assert the output lists the ordered PlannedRequest items. Write a second test that runs the real command against a fake runner that records each call, and compares the recorded calls with the plan, and verify that `uv run devops ci test tests/test_repos_dry_run.py` fails on the base
- [ ] 4.2 Add --dry-run to repos clone, repos clone-org, repos sync, and repos update. In the dry-run path, build each PlannedRequest from the same argument builder the real run uses (clone_repo and fetch_all in git/operations.py, and the GitHub org listing for clone-org). Return the command's real result type marked as a dry run with the ordered PlannedRequest items. Print with render_request_plan. Give all four commands the request-plan class. Remove the echo-only --dry-run options and render_dry_run_result calls. Remove the four entries (repos clone, repos clone-org, repos sync, repos update) from tests/fixtures/dry_run_gaps.json, and verify that `uv run devops ci test tests/test_repos_dry_run.py` passes
- [ ] 4.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 5. Mark-only ssh: audit, generate, list, status

Reads: none. Changes: `src/devops_cli/commands/ssh.py`, `tests/fixtures/dry_run_gaps.json`, `tests/test_ssh_dry_run.py`.

- [ ] 5.1 Write a test that runs devops --dry-run ssh audit, devops --dry-run ssh generate, devops --dry-run ssh list, and devops --dry-run ssh status with the process runner and HTTP clients patched to fail. Assert each command completes and returns its normal result. Assert ssh list has no echo-only --dry-run option, and verify that `uv run devops ci test tests/test_ssh_dry_run.py` fails on the base
- [ ] 5.2 Add the no-external-request class to ssh audit, ssh generate, ssh list, and ssh status. Remove the echo-only --dry-run option and render_dry_run_result call from ssh list (named in #886). Remove the four entries (ssh audit, ssh generate, ssh list, ssh status) from tests/fixtures/dry_run_gaps.json, and verify that `uv run devops ci test tests/test_ssh_dry_run.py` passes
- [ ] 5.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 6. Request-plan ssh: register, rotate

Reads: none. Changes: `src/devops_cli/commands/ssh.py`, `tests/fixtures/dry_run_gaps.json`, `tests/test_ssh_dry_run.py`.

- [ ] 6.1 Write a test that runs devops ssh register --dry-run and devops ssh rotate --dry-run with the HTTP client (httpx2.AsyncClient) patched to raise. Assert no external request is made. Assert the output lists the ordered PlannedRequest items with argv, stdin, env, condition and repeat. Write a second test that runs the real command against a fake HTTP client that records each call, and compares the recorded calls with the plan, and verify that `uv run devops ci test tests/test_ssh_dry_run.py` fails on the base
- [ ] 6.2 Add --dry-run to ssh register and ssh rotate. In the dry-run path, build each PlannedRequest from the same argument builder the real run uses (the GitHub session post for key registration and rotation). Return the command's real result type marked as a dry run with the ordered PlannedRequest items. Print with render_request_plan. Give both commands the request-plan class. Remove the echo-only --dry-run options and render_dry_run_result calls. Remove the two entries (ssh register, ssh rotate) from tests/fixtures/dry_run_gaps.json, and verify that `uv run devops ci test tests/test_ssh_dry_run.py` passes
- [ ] 6.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 7. Mark-only tls: ca, cert, homelab, inspect, verify

Reads: none. Changes: `src/devops_cli/commands/tls.py`, `tests/fixtures/dry_run_gaps.json`, `tests/test_tls_dry_run.py`.

- [ ] 7.1 Write a test that runs devops --dry-run tls ca, devops --dry-run tls cert, devops --dry-run tls homelab, devops --dry-run tls inspect, and devops --dry-run tls verify with the process runner and HTTP clients patched to fail. Assert each command completes and returns its normal result. Assert tls ca, tls cert, and tls homelab have no echo-only --dry-run option, and verify that `uv run devops ci test tests/test_tls_dry_run.py` fails on the base
- [ ] 7.2 Add the no-external-request class to tls ca, tls cert, tls homelab, tls inspect, and tls verify. Remove the echo-only --dry-run options and render_dry_run_result calls from tls ca, tls cert, and tls homelab. Remove the five entries (tls ca, tls cert, tls homelab, tls inspect, tls verify) from tests/fixtures/dry_run_gaps.json, and verify that `uv run devops ci test tests/test_tls_dry_run.py` passes
- [ ] 7.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 8. Request-plan tls: enable-k8s

Reads: none. Changes: `src/devops_cli/commands/tls.py`, `tests/fixtures/dry_run_gaps.json`, `tests/test_tls_dry_run.py`.

- [ ] 8.1 Write a test that runs devops tls enable-k8s --dry-run with kubectl patched to raise. Assert no external request is made. Assert the output lists the ordered PlannedRequest items with argv, stdin, env, condition and repeat. Write a second test that runs the real command against a fake process runner that records each call, and compares the recorded calls with the plan, and verify that `uv run devops ci test tests/test_tls_dry_run.py` fails on the base
- [ ] 8.2 Add --dry-run to tls enable-k8s. In the dry-run path, build each PlannedRequest from the same argument builder the real run uses (the kubectl create call at commands.tls:enable_k8s_cmd:508). Return the command's real result type marked as a dry run with the ordered PlannedRequest items. Print with render_request_plan. Give the command the request-plan class. Remove the echo-only --dry-run option and render_dry_run_result call. Remove the entry (tls enable-k8s) from tests/fixtures/dry_run_gaps.json, and verify that `uv run devops ci test tests/test_tls_dry_run.py` passes
- [ ] 8.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 9. Ratchet test and full CI verification

Reads: none. Changes: `tests/test_roadmap_dry_runs.py`.

- [ ] 9.1 Run the ratchet test from sub-issue 00 and confirm it passes with all 24 commands removed from tests/fixtures/dry_run_gaps.json. Run the full test suite for the four command families and confirm no test starts a process or opens a socket, and verify that `uv run devops ci` fails on the base
- [ ] 9.2 Verify that tests/fixtures/dry_run_gaps.json no longer contains any of the 24 commands. Confirm the ratchet test in tests/test_roadmap_dry_runs.py passes. If the ratchet test needs an update to reflect the new class assignments, add the assertion that each of the 24 commands carries the correct class (request-plan or no-external-request), and verify that `uv run devops ci` passes
- [ ] 9.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

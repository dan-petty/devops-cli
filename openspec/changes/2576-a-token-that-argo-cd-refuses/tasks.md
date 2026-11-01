# Tasks

## 1. Add argocd_api_request helper

Reads: none. Changes: `src/devops_cli/argo/credentials.py`.

- [ ] 1.1 Write a test that mocks the HTTP client to return 401, then verifies argocd_api_request mints a new token via mint_argocd_token, stores it, and retries the request. Write a test for 401 without password that verifies ArgoError is raised with a message naming argocd.token. Write a test for retry 401 that verifies ArgoError is raised. Write a test for HTTP 500 that verifies ArgoError is raised with the status code in the message, and verify that `uv run devops ci test tests/test_argo_credentials.py` fails on the base
- [ ] 1.2 Add argocd_api_request to src/devops_cli/argo/credentials.py. It takes the client, method, url, headers, json body, timeout, and settings. It makes the request. On 401 with a stored password, it calls mint_argocd_token, updates the Authorization header, and retries once. On 401 without a password, it raises ArgoError naming argocd.token and devops k8s credentials sync. On retry 401, it raises ArgoError. On any other non-2xx status, it raises ArgoError with the status code. On success, it returns the response, and verify that `uv run devops ci test tests/test_argo_credentials.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Update cd_apps_sync to use the helper

Reads: none. Changes: `src/devops_cli/commands/argo.py`.

- [ ] 2.1 Write a test that mocks the Argo CD API to return 401, then verifies cd_apps_sync retries with a new token and succeeds. Write a test that verifies cd_apps_sync raises ArgoError on 401 without password, with no traceback, and verify that `uv run devops ci test tests/test_argo_commands.py` fails on the base
- [ ] 2.2 In cd_apps_sync, replace the client.post and resp.raise_for_status pattern with a call to argocd_api_request. Pass the settings so the helper can mint a token on 401. Remove the direct raise_for_status call, and verify that `uv run devops ci test tests/test_argo_commands.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Update cd_apps_list and cd_apps_status to use the helper

Reads: none. Changes: `src/devops_cli/commands/argo.py`.

- [ ] 3.1 Write a test that mocks the Argo CD API to return 401, then verifies cd_apps_list retries with a new token. Write a test that verifies cd_apps_status raises ArgoError on 401 without password, with no traceback, and verify that `uv run devops ci test tests/test_argo_commands.py` fails on the base
- [ ] 3.2 In cd_apps_list and cd_apps_status, replace the client.get and resp.raise_for_status pattern with a call to argocd_api_request. Pass the settings so the helper can mint a token on 401. Remove the direct raise_for_status call, and verify that `uv run devops ci test tests/test_argo_commands.py` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

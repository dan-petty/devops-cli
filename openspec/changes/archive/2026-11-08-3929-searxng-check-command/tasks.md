# Tasks

## 1. The rows and the judgment of a reply

Kind: behavior. Reads: `src/devops_cli/k8s/crawl4ai_check.py`, `src/devops_cli/k8s/service_probe.py`, `src/devops_cli/ai/web_search.py`, `tests/invariants/test_k8s_searxng.py`. Changes: `tests/k8s/test_searxng_check.py` (new), `src/devops_cli/k8s/searxng_check.py` (new).

- [x] 1.1 Write `tests/k8s/test_searxng_check.py`. The tests assert `reply_problems` for a full reply, a missing key, an `unresponsive_engines` that is no list, a 403, an empty `results`, an engine that stays off in `results` and in `unresponsive_engines`, an engine that the caller names, and a body that is no JSON object, and they assert the shape of `SEARXNG_IMAGE` and the reuse of the shared probe code. Run it and see it fail
  - Verification: `$ uv run devops ci test tests/k8s/test_searxng_check.py` fails on the base
- [x] 1.2 Add `src/devops_cli/k8s/searxng_check.py` with `SEARXNG_IMAGE`, `REPLY_KEYS`, `OFF_ENGINES`, the six row names, the request of each row, and `reply_problems`
  - Verification: `$ uv run devops ci test tests/k8s/test_searxng_check.py` passes

## 2. The command

Kind: behavior. Reads: `src/devops_cli/commands/k8s/crawl4ai_check.py`, `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/support/kubectl_calls.py`. Changes: `tests/commands/k8s/test_k8s_searxng_check.py` (new), `tests/support/kubectl_calls.py`, `tests/commands/k8s/test_k8s_crawl4ai_check.py`, `src/devops_cli/commands/k8s/searxng_check.py` (new), `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/config/defaults.py`.

- [x] 2.1 Write `tests/commands/k8s/test_k8s_searxng_check.py`. The tests assert the six requests, the reply keys, the categories, the 403, the engines that stay off, the two bang rows, the unused category, the two pods and their probes, the roles in the output, the forward that ends at once, the health route that gives no answer, the context option and the dry run. Move the fake forward child into `tests/support/kubectl_calls.py` for both command tests. Run them and see them fail
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_searxng_check.py` fails on the base
- [x] 2.2 Add `src/devops_cli/commands/k8s/searxng_check.py` in the shape of `k8s crawl4ai-check`: the options `--local-port`, `--context` and `--dry-run`, the class `request-plan`, the tables, and the exit 1 on a problem row or a reached destination. Register it as `searxng-check`, and add its messages, help texts and `DEFAULT_SEARXNG_CHECK_LOCAL_PORT`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_searxng_check.py tests/commands/k8s/test_k8s_crawl4ai_check.py tests/invariants/test_dry_run_class_ratchet.py` passes

## 3. Fail the gate on an image bump

Kind: other. Reads: `tests/gate/k8s_checks/devops_runtime.py`, `tests/invariants/test_k8s_searxng.py`, `k8s/devops/searxng/deployment.yaml`. Changes: `tests/gate/k8s_checks/devops_runtime.py`, `tests/invariants/test_k8s_searxng.py`.

- [x] 3.1 Make the check of Deployment `searxng` in `tests/gate/k8s_checks/devops_runtime.py` compare the full image with `SEARXNG_IMAGE`, and name both images and the command in the failure text
  - Verification: `$ uv run devops ci --only k8s` passes
- [x] 3.2 Make `tests/invariants/test_k8s_searxng.py` import `OFF_ENGINES` from `devops_cli.k8s.searxng_check` and delete its own `FORBIDDEN_ENGINES`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py` passes

## 4. Documents

Kind: documents. Reads: `k8s/README.md`, `docs/commands/k8s.md`. Changes: `k8s/README.md`, `docs/commands/k8s.md`, `docs/CLI_REFERENCE.md`, `README.md`.

- [x] 4.1 In the SearXNG section of `k8s/README.md`, add a bullet that names the command, what it checks, that a person runs it at each bump of the digest, and that the `k8s` row of `devops ci` fails until `SEARXNG_IMAGE` matches
  - Verification: `$ uv run devops ci docs` passes
- [x] 4.2 Run `uv run devops docs generate --sync-readme` so the command documents list `devops k8s searxng-check`
  - Verification: `$ uv run devops ci docs` passes

## 5. The reply fixture of the pinned image

Kind: other. Reads: `tests/ai/test_web_search_searxng.py`, `tests/fixtures/searxng/search_reply.json`. Changes: `tests/k8s/test_searxng_check.py`, `tests/ai/test_web_search_searxng.py`, `tests/fixtures/searxng/search_reply.json`, `tests/fixtures/searxng/search_reply_image.txt` (new).

- [x] 5.1 Run `uv run devops k8s searxng-check` once against the cluster through a port-forward, and save one live reply of the pinned image (the `it` row, cut to its first three hits, because the `general` row gave one hit while duckduckgo answered CAPTCHA) as `tests/fixtures/searxng/search_reply.json`, with each private value masked. Write `SEARXNG_IMAGE` into `tests/fixtures/searxng/search_reply_image.txt`
  - Verification: `$ uv run devops ci test tests/ai/test_web_search_searxng.py` passes
- [x] 5.2 Add a test to `tests/k8s/test_searxng_check.py` that the fixture holds the seven reply keys, no engine of `OFF_ENGINES`, and that the file next to it holds `SEARXNG_IMAGE`
  - Verification: `$ uv run devops ci test tests/k8s/test_searxng_check.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

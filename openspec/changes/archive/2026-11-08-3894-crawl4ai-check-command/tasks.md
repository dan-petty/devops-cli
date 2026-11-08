# Tasks

## 1. Probe from a throwaway pod

Reads: `src/devops_cli/core/process.py`, `src/devops_cli/exceptions/k8s.py`, `k8s/namespaces.yaml`, `k8s/devops/crawl4ai/networkpolicy.yaml`. Changes: `tests/k8s/test_service_probe.py` (new), `tests/support/kubectl_calls.py` (new), `src/devops_cli/k8s/service_probe.py` (new), `src/devops_cli/exceptions/k8s.py`.

- [x] 1.1 Write `tests/k8s/test_service_probe.py` and `tests/support/kubectl_calls.py`. The tests assert the blocked and reached rows, the labels and namespace of the pod, the image digest, the `restricted` security context, the readiness probe that runs `false`, the order of run, exec and delete, the context option and the delete after a failure. Run it and see it fail
  - Verification: `$ uv run devops ci test tests/k8s/test_service_probe.py` fails on the base
- [x] 1.2 Add `ServiceProbeError` (`K8S_SERVICE_PROBE_ERROR`) to `src/devops_cli/exceptions/k8s.py`. Add `src/devops_cli/k8s/service_probe.py` with `PodTarget`, `PodProbeRow` and `probe_from_pod`. Choose a small public image that has a shell and a TCP client, pin it by digest, and read the documentation of its client applet to choose the probe command. Write the choice and its source in the module docstring
  - Verification: `$ uv run devops ci test tests/k8s/test_service_probe.py` passes

## 2. The check of the Crawl4AI service

Reads: `src/devops_cli/commands/k8s/image_pins.py`, `src/devops_cli/ai/page_text.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`. Changes: `tests/k8s/test_crawl4ai_check.py` (new), `tests/commands/k8s/test_k8s_crawl4ai_check.py` (new), `src/devops_cli/k8s/crawl4ai_check.py` (new), `src/devops_cli/commands/k8s/crawl4ai_check.py` (new), `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/config/defaults.py`.

- [x] 2.1 Write `tests/k8s/test_crawl4ai_check.py` and `tests/commands/k8s/test_k8s_crawl4ai_check.py`. The tests assert the 25 requests, the requests without the token, the served page, the fault, the report rows, the roles in the output, the token handling, the missing keyring entry, the forward that ends at once, the NetworkPolicy rows, the context option and the dry run. Run them and see them fail
  - Verification: `$ uv run devops ci test tests/k8s/test_crawl4ai_check.py tests/commands/k8s/test_k8s_crawl4ai_check.py` fails on the base
- [x] 2.2 Add `src/devops_cli/k8s/crawl4ai_check.py` with `CRAWL4AI_IMAGE`, the routes, the target roles composed at run time, `is_refusal` and the function that sends the matrix and the requests without the token. Add the default port to `src/devops_cli/config/defaults.py`
  - Verification: `$ uv run devops ci test tests/k8s/test_crawl4ai_check.py` passes
- [x] 2.3 Add the command in `src/devops_cli/commands/k8s/crawl4ai_check.py` in the shape of `k8s image-pins`: the options `--local-port`, `--context` and `--dry-run`, the class `request-plan`, the report tables, and the exit 1 on a served target, an unrefused request without the token or a reached destination. Register it as `crawl4ai-check` in `src/devops_cli/commands/k8s/__init__.py`, and add its messages and help texts
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_crawl4ai_check.py tests/invariants/test_dry_run_class_ratchet.py` passes

## 3. Fail the gate on an image bump

Reads: `tests/gate/k8s_checks/devops_runtime.py`, `k8s/devops/crawl4ai/deployment.yaml`. Changes: `tests/gate/k8s_checks/devops_runtime.py`.

- [x] 3.1 Make the check of Deployment `crawl4ai` in `tests/gate/k8s_checks/devops_runtime.py` compare the full image with `CRAWL4AI_IMAGE`, and name both images and the command in the failure text
  - Verification: `$ uv run devops ci --only k8s` passes

## 4. Documents

Reads: `k8s/README.md`, `docs/commands/k8s.md`. Changes: `k8s/README.md`, `docs/commands/k8s.md`, `docs/CLI_REFERENCE.md`, `README.md`.

- [x] 4.1 In the Crawl4AI section of `k8s/README.md`, add a bullet that names the command, what it checks, that a person runs it at each bump of the digest, and that the `k8s` row of `devops ci` fails until `CRAWL4AI_IMAGE` matches
  - Verification: `$ uv run devops ci docs` passes
- [x] 4.2 Run `uv run devops docs generate --sync-readme` so the command documents list `devops k8s crawl4ai-check`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- The manual run with `CRAWL4AI_ALLOW_INTERNAL_URLS=true` is tracked in #4018, and the redirect case in #4019. The SearXNG check of #3929 reuses `src/devops_cli/k8s/service_probe.py`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

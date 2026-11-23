# Tasks

## 1. The HTTP attempt from the throwaway pod

Kind: behavior. Reads: `src/devops_cli/k8s/service_probe.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/core/process.py`, `src/devops_cli/core/clock.py`, `src/devops_cli/dry_run/requests.py`, `src/devops_cli/lang/en/errors.py`, `tests/k8s/test_service_probe.py`, `tests/support/fakes/process.py`, `tests/support/fakes/clock.py`, `tests/support/kubectl_calls.py`. Changes: `src/devops_cli/k8s/service_probe.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/errors.py`, `tests/k8s/test_service_probe.py`.
Adds: `CURL_IMAGE`, `PodHttpResult`, `probe_http_from_pod`, `plan_probe_http_from_pod`, `_request_from_pod`, `_curl_exit`, `DEFAULT_PROBE_WAIT_SECONDS`, `DEFAULT_PROBE_TIMEOUT_SECONDS`, `DEFAULT_PROBE_RETRY_SECONDS`

- [x] 1.1 `tests/k8s/test_service_probe.py::test_a_blocked_path_prints_the_curl_exit_code_at_the_wait_deadline` fails on the base
  - Verification: `$ uv run devops ci test tests/k8s/test_service_probe.py` fails on the base
- [x] 1.2 Write the failing tests first in `tests/k8s/test_service_probe.py`, in the shape of `def _probe(**overrides: Any)` and the process fake. Add `PodHttpResult` with `status` and `curl_exit`, `probe_http_from_pod`, `plan_probe_http_from_pod`, `_request_from_pod` and `_curl_exit` to `src/devops_cli/k8s/service_probe.py`. `probe_http_from_pod` takes the namespace, the labels, the URL, the method, the headers, the image, the wait, the timeout, the name prefix and the context; it starts one pod with `_start_pod(name, namespace, labels, context, image=image)`, sends each attempt with one `kubectl exec -i` of `curl -sS -o /dev/null -w %{http_code} -K - <url>` under the connect bound of `DEFAULT_PROBE_CONNECT_SECONDS`, writes each header as a `header = "<value>"` line on the standard input of `run_subprocess`, and reads the remote exit code from the `command terminated with exit code` line. The loop checks the `--timeout` deadline first and raises the timeout text when the clock passes it, returns `PodHttpResult(curl_exit=7)` when the clock passes the `--wait` deadline with exit 7, and returns the first attempt that is no 7; it sleeps `DEFAULT_PROBE_RETRY_SECONDS` between attempts and deletes the pod in the `except BaseException` block that `probe_from_pod` uses. `plan_probe_http_from_pod` renders the run call with the restricted pod spec, one exec per attempt with its curl command line, the URL and a placeholder for the headers, and the delete call. Make `image` a required keyword argument of `_pod_overrides`, `_run_argv` and `_start_pod`, pass `PROBE_IMAGE` from `probe_from_pod` and `plan_probe_from_pod`, add `CURL_IMAGE` with the curlimages/curl tag and the digest that `tag_digest` reads once, and add `DEFAULT_PROBE_WAIT_SECONDS`, `DEFAULT_PROBE_TIMEOUT_SECONDS` and `DEFAULT_PROBE_RETRY_SECONDS` to `src/devops_cli/config/defaults.py` and the timeout text to `src/devops_cli/lang/en/errors.py`
  - Verification: `$ uv run devops ci test tests/k8s/test_service_probe.py` passes

## 2. The probe subcommand of the k8s group

Kind: behavior. Reads: `src/devops_cli/commands/k8s/searxng_check.py`, `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/k8s/service_probe.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/dry_run/requests.py`, `tests/commands/k8s/test_k8s_searxng_check.py`, `tests/support/fakes/process.py`, `tests/support/kubectl_calls.py`, `tests/commands/k8s/test_bootstrap_roadmap_key.py`, `tests/invariants/test_dry_run_class_ratchet.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/commands/k8s/probe.py` (new), `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/k8s/test_k8s_probe.py` (new).
Adds: `k8s_probe`

- [x] 2.1 `tests/commands/k8s/test_k8s_probe.py::test_a_blocked_path_prints_the_curl_exit_code` fails on the base
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_probe.py` fails on the base
- [x] 2.2 Write the failing tests first in `tests/commands/k8s/test_k8s_probe.py`, which drives the command through the cli fixture and the process fake, in the shape of `tests/commands/k8s/test_k8s_searxng_check.py` and its `_check` helper. Add `k8s_probe` to `src/devops_cli/commands/k8s/probe.py` in the shape of `src/devops_cli/commands/k8s/searxng_check.py` and its `@dry_run_class("request-plan")`: the options `--label`, `--url`, `--method`, `--header`, `--namespace`, `--image`, `--wait`, `--timeout`, `--context` and `--dry-run`, a refusal of an `--image` value that holds no `@sha256:` before any kubectl call, the plan of `plan_probe_http_from_pod` under `--dry-run`, and the print `status=<code>` or `curl_exit=<code>`. It passes `CURL_IMAGE`, or the `--image` value, to `probe_http_from_pod`. Exit 0 on a measured result and raise `ServiceProbeError` when the run measured nothing. Register it as `app.command("probe")(k8s_probe)` in `src/devops_cli/commands/k8s/__init__.py`, and add its option help to `src/devops_cli/lang/en/help.py` and its texts to `src/devops_cli/lang/en/messages.py`. The generated documents follow in the next group
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_probe.py` passes

## 3. Regenerate the command documents

Kind: other. Reads: `docs/commands/k8s.md`, `docs/CLI_REFERENCE.md`, `src/devops_cli/commands/k8s/probe.py`. Changes: `docs/commands/k8s.md`, `docs/CLI_REFERENCE.md`.

- [x] 3.1 Run `uv run devops docs generate` so `docs/commands/k8s.md` holds the new subcommand, its options and its docstring, and `docs/CLI_REFERENCE.md` lists it under the k8s group. The generator writes both files, and nobody edits them by hand
  - Verification: `$ uv run devops ci docs` passes
- [x] 3.2 Regenerate `docs/commands/k8s.md` and `docs/CLI_REFERENCE.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

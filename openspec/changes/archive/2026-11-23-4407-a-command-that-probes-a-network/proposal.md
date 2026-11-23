# Proposal

## Why

A network policy path is proven today with a hand-made pod: `kubectl run --overrides` with a restricted security context, a label and a sleep (#4407). The first attempt fails because kube-router programs the policy a few seconds after the pod starts, and the steps are easy to get wrong. #4407 replaces them with one subcommand of the `k8s` group that retries until the policy is programmed, measures one request, prints the status or the curl exit code, and always deletes its pod.

## What Changes

- Add `PodHttpResult`, `probe_http_from_pod`, `plan_probe_http_from_pod`, `_request_from_pod` and `_curl_exit` beside `src/devops_cli/k8s/service_probe.py:194:def _connects(name: str, namespace: str, target: PodTarget, context: str | None) -> bool:`: one `kubectl exec -i` of curl per attempt, the retry while curl exits 7, the wait and timeout deadlines, and the pod delete of the existing `except BaseException` block.
- Make `image` a required keyword argument of `_pod_overrides`, `_run_argv` and `_start_pod`, pass `PROBE_IMAGE` from `probe_from_pod` and `plan_probe_from_pod`, and add `CURL_IMAGE` for curlimages/curl pinned by digest.
- Add the `probe` subcommand of the `k8s` group in `src/devops_cli/commands/k8s/probe.py` with `--label`, `--url`, `--method`, `--header`, `--namespace`, `--image`, `--wait`, `--timeout`, `--context` and `--dry-run`, and register it beside `src/devops_cli/commands/k8s/__init__.py:90:app.command("searxng-check")(k8s_searxng_check)`.
- Send each header value to curl as a config line on the standard input of the exec call, so no argv and no output holds the value.
- Retry while curl exits 7 and end at the `--wait` deadline with `curl_exit=<code>` and exit 0, stop at the `--timeout` deadline with a timeout error and a non-zero exit, and print `status=<code>` for a response.
- Delete the pod also after an error or a timeout.
- Add `DEFAULT_PROBE_WAIT_SECONDS`, `DEFAULT_PROBE_TIMEOUT_SECONDS` and `DEFAULT_PROBE_RETRY_SECONDS` beside `src/devops_cli/config/defaults.py:714:DEFAULT_PROBE_CONNECT_SECONDS: int = 3`, and regenerate `docs/commands/k8s.md` and `docs/CLI_REFERENCE.md` with `uv run devops docs generate`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `k8s-probe`: One labeled probe pod, Restricted security context, Wait for the policy, Blocked result, Probe deadline, Credential off the command line, Pod deletion, Dry run, Pinned image

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/k8s/service_probe.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/commands/k8s/probe.py`, `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/commands/k8s.md`, `docs/CLI_REFERENCE.md`
- Tests: `tests/k8s/test_service_probe.py`, `tests/commands/k8s/test_k8s_probe.py`

## Feasibility

- probes answered, word for word: The path `app.kubernetes` is no file of the staging commit. No commit in the history deleted or renamed it. That name is the label key of the Done-when section, not a repository path, so no file is missing.
- `read_file` returned `src/devops_cli/k8s/service_probe.py:267:def probe_from_pod(` and `src/devops_cli/k8s/service_probe.py:62:PROBE_IMAGE = (`, the one-pod probe and its pinned image that the command extends, and `list_files` of `src/devops_cli/commands/k8s` listed no probe module, so the subcommand is new.
- `read_file` returned `src/devops_cli/k8s/service_probe.py:65:_KUBECTL_TIMEOUT_SECONDS = 30` for the bound of each kubectl call.
- `read_file` returned `src/devops_cli/k8s/service_probe.py:67:_EXEC_TERMINATED = "command terminated with exit code"`, which reads the remote exit code of a command in the pod.
- `read_file` returned `src/devops_cli/k8s/service_probe.py:306:def plan_probe_from_pod(`, which renders the pod calls with no cluster call, and `src/devops_cli/k8s/service_probe.py:289:except BaseException:`, the deletion that also runs after a failure.
- `read_file` returned `src/devops_cli/k8s/service_probe.py:124:def _pod_overrides(name: str) -> dict[str, object]:` with `src/devops_cli/k8s/service_probe.py:128:"runAsNonRoot": True` and `src/devops_cli/k8s/service_probe.py:131:"seccompProfile": {"type": "RuntimeDefault"},`, which already set the restricted level, and `src/devops_cli/k8s/service_probe.py:218:def _start_pod(name: str, namespace: str, labels: Mapping[str, str], context: str | None) -> None:`.
- `read_file` returned `src/devops_cli/config/defaults.py:713:DEFAULT_PROBE_POD_START_SECONDS: int = 120`, `src/devops_cli/config/defaults.py:714:DEFAULT_PROBE_CONNECT_SECONDS: int = 3` and `src/devops_cli/config/defaults.py:716:DEFAULT_PROBE_POD_LIFETIME_SECONDS: int = 600`, the staged bounds that the probe reuses; the wait, timeout and retry bounds are new and take one new name each.
- `search_code` for `input: str | None = None` returned `src/devops_cli/core/process.py:1040:input: str | None = None` and `tests/support/fakes/process.py:39:stdin: str | bytes | None = None`, so the exec call takes the header values on its standard input and the process fake records them.
- `read_file` returned `tests/k8s/test_service_probe.py:41:def _probe(**overrides: Any) -> list[PodProbeRow]:`, the helper that already drives the pod with the process fake, so the new cases join that module.
- `read_file` returned `tests/support/kubectl_calls.py:40:def verb(argv: Sequence[str]) -> str:`, which names a recorded call by its verb, so a test counts the run and exec calls without a position.
- `read_file` returned `tests/commands/k8s/test_k8s_searxng_check.py:145:def _check(cli: Callable[..., Any], *args: str) -> Any:`, the shape of a k8s command test that drives the cli fixture, and `src/devops_cli/commands/k8s/searxng_check.py:100:@dry_run_class("request-plan")` with `src/devops_cli/commands/k8s/searxng_check.py:135:raise ServiceProbeError(`, the dry-run plan and the failing exit that the new command copies.
- `read_file` returned `src/devops_cli/commands/k8s/__init__.py:90:app.command("searxng-check")(k8s_searxng_check)`, where the new subcommand registers beside the existing k8s checks.
- `read_file` returned `src/devops_cli/dry_run/requests.py:27:stdin: str | None = None`, whose field holds a named placeholder for a value that the dry run never prints.
- `read_file` returned `src/devops_cli/lang/en/errors.py:194:probe_pod_failed: str = "The probe pod {pod} failed at step {step}: {detail}"`, the k8s error block that the timeout text joins, and `src/devops_cli/lang/en/messages.py:845:crawl4ai_check_dry_run: str = (`, the dry-run note of a k8s check.
- `search_code` for `CURL_IMAGE` returned no match, so the plan adds that name and copies no existing one; `search_code` for `def k8s_probe` returned no match too, so the subcommand is new.
- `read_file` returned `src/devops_cli/docker/registry.py:102:def tag_digest(reference: str, client: httpx2.Client, *, timeout: float) -> str:`, the project's reader of a tag digest, which the implement step runs once to write the literal of `CURL_IMAGE`.
- `read_file` returned `tests/invariants/test_dry_run_class_ratchet.py:30:CONST_GAPS_FILE = FIXTURES / "dry_run_gaps.json"`, the gaps list that a command with a declared dry-run class never joins, so the new subcommand declares one and no gaps file changes.
- `find_issues` for `k8s probe network policy` listed #6666, which runs the probe command of this item on the live cluster and so comes after it, and `read_issue` showed #4355 closed and completed, so no item must be delivered first.
- Precondition of `probe_http_from_pod(...)`: a client of the cluster, because it starts the pod with `kubectl run`, sends each attempt with `kubectl exec -i` and deletes the pod with `kubectl delete`; no checkout of the repository and no other network.
- Precondition of `plan_probe_http_from_pod(...)`: none, because it builds the argv and the curl command line and starts no process.
- Precondition of `k8s_probe(...)`: a client of the cluster, which it passes to `probe_http_from_pod`; no checkout of the repository and no other network.
- Precondition of `tag_digest(...)`: a network to the image registry, because it reads the manifest of a tag through an HTTP client; no checkout of the repository and no cluster.
- The verify `uv run devops ci test tests/k8s/test_service_probe.py` needs the failure class `test`; `uv`, `python` and `devops` are runner tools of the image, and the process fake answers for `kubectl`, so the test reaches no cluster and no network.
- The verify `uv run devops ci test tests/commands/k8s/test_k8s_probe.py` needs the failure class `test`; `uv`, `python` and `devops` are runner tools of the image, and the process fake answers for `kubectl`.
- The verify `uv run devops ci docs` needs the failure class `lint`; `uv` and `devops` are runner tools of the image, and the generator writes only inside the workspace of the step.
- `docker` is `NOT_IN_RUNNER`, because the runner pod runs no container engine and drops all capabilities, so the implement step reads the digest with `tag_digest` and never with a Docker command.
- The pod settings of the runner are `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`, and no step of this plan needs another setting.
- The first live check runs after the merge on a host with a client of the cluster: the `probe` subcommand that the change adds, with `--label app.kubernetes.io/name=devops-cli-job` and the URL `http://<mcp-service>:8001/implementation/mcp`, prints `status=401`, and the same run with another label prints `curl_exit=7` and exits 0. The subcommand is not in the staged tree, so this run gives no command line for it.
- The second live check runs the same subcommand with `--dry-run` and prints the `kubectl run` call, the curl command line and the URL with no kubectl call; a pod that cannot pull the pinned digest stops with the error text of `src/devops_cli/lang/en/errors.py:194:probe_pod_failed: str = "The probe pod {pod} failed at step {step}: {detail}"` and has the failure class `premise_false`, because the cluster then differs from the plan.
- not checked: that the pinned curl image holds `sleep`, `sh` and `curl` for a non-root user, because this run reaches no registry and no cluster; the first live check proves it.
- not checked: the digest that the curl tag names now, because this run reads no registry; the implement step reads it once with `tag_digest` and writes the literal into `CURL_IMAGE`.

## Existing Tool Considered

kubectl (Apache-2.0, maintained) creates the labeled pod, sends the request and deletes the pod, and the pinned image curlimages/curl supplies curl and its exit codes; the wait for the policy, the restricted context, the printed result and the cleanup on timeout are the project's own code, at about 25k tokens to build, about 5k tokens a year to keep and fix, and about 4 hours of elapsed time. The change deletes no module and extends the shared probe module.

## Dependencies

None.

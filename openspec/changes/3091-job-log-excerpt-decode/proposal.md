# Proposal

## Why

Issue #3091: the comment that reports an ended runner Job shows the log excerpt as `b'Tool call: read_file, ok.\nTool call: ...'`. It is a bytes literal with `\n` in place of line breaks and `\xe2\x9c\x93` in place of a check mark. The reader cannot read the comment or copy a command from it. The mask of secrets also runs on this escaped text, not on the text that the pod wrote.

The issue names `str(log)` in `ClusterJobs.log_tail` as the cause and says that the client returns `bytes`. The real cause is one step earlier, in the Kubernetes client (see Feasibility). The fix reads the log without the client's lossy conversion and decodes it once, in one place. The doctor reads pod logs through the same call and has the same defect, so this change fixes both.

## What Changes

- Add `read_pod_log_text` to `devops_cli.k8s.service`. It asks the client for the raw response (`_preload_content=False`) and decodes it as UTF-8 with replacement, with the reader that `PodLogStream` already has. It returns text with real line breaks.
- `ClusterJobs.log_tail` and the doctor snapshot (`k8s/doctor.py`) call it.
- The report comment of an ended Job shows the excerpt in a fenced block, as the stop comment already shows a diff. The fence is one backtick longer than the longest run of backticks in the text. The mask of secrets runs on the decoded text.
- `code_fence` moves to a small module and the stop comment uses it too, so the fence rule has one home.
- The pod log of `FakeCoreV1` takes `bytes`, and answers as the real client does: a plain read gives the escaped text, a raw read gives the bytes.
- This change alters observable output (the comment of the Service and the log lines of `devops k8s doctor`), so it carries spec deltas.
- This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `roadmap-implement-job`: the report of an ended Job shows decoded, masked text in a fenced block.
- `k8s-doctor`: the log lines of the snapshot are decoded text.

## Impact

- `src/devops_cli/k8s/service.py`, `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/k8s/doctor.py`.
- `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/fence.py` (new), `src/devops_cli/lang/en/messages.py`.
- `tests/support/fakes/kubernetes.py`, `tests/k8s/`, `tests/roadmap/test_roadmap_implement_submit.py`.

## Feasibility

The premise in the issue is wrong in one detail, and the goal is still reachable. The evidence:

- Source of `kubernetes` 36.0.3 (the version in `uv.lock`). `CoreV1Api.read_namespaced_pod_log` sets `response_types_map = {200: "str"}`. In `ApiClient.__call_api` the decode of the body to text runs only `if response_type not in ["file", "bytes", "str"]`, so a `str` response is not decoded. `ApiClient.deserialize` then runs `json.loads(response.data)` on the raw bytes. A log is not JSON, so this raises `ValueError`, and `data` stays `bytes`. `__deserialize_primitive` returns `str(data)`.
- So the client itself returns a `str` that holds the repr of the bytes. Without `_preload_content=False`, `read_namespaced_pod_log` never returns `bytes`. `str(log)` in `log_tail` changes nothing, and a fix that decodes `bytes` there would never run against a real cluster.
- A log that is valid JSON, such as `{"k": 1}`, is parsed and returned as the repr of a Python dict (`{'k': 1}`). That is a second wrong result of the same cause.
- Command output. A probe script in `.data/agent/scratch/` served `Tool call: read_file, ok.\nline <U+2713> two\n` from a loopback HTTP server to a real `CoreV1Api(ApiClient(Configuration(host=...)))`. The call returned type `str` with the value `"b'Tool call: read_file, ok.\\nline \\xe2\\x9c\\x93 two\\n'"`, and `{"k": 1}` came back as `"{'k': 1}"`. The live comments on #2175 of 2026-11-01 show the same text.
- With `_preload_content=False` the client returns the `urllib3` response. `KubernetesService.read_pod_logs` and `PodLogStream` already use this path and decode UTF-8 with replacement. The test of this change reads the same loopback body through the real client and gets the check mark.
- The same call, `read_namespaced_pod_log` without `_preload_content=False`, is in `k8s/doctor.py`. It has the same defect: `raw_log.splitlines()` sees one line.
- The Service pod read of a finished runner Job was not needed: the comments on #2175 are the real output, and the loopback probe reproduces them with the real client.

The change fits one pull request: two source modules read a log, one module writes the comment, and the tests are small.

## Existing Tool Considered

- The `kubernetes` client with `_preload_content=False` is the documented way to get the raw response. `PodLogStream` of this repository already decodes it (`codecs.getincrementaldecoder("utf-8")("replace")`), so no new decoder is written.
- A newer `kubernetes` release might fix the conversion. `uv.lock` pins 36.0.3, which is the current release, and the upstream conversion code is unchanged in the source that was read. The test of the change reads a body through the real client, so a client that fixes the conversion would not break the test, and the raw read stays correct.
- CommonMark fences: the stop comment already computes a fence that no line of the text can end. This change reuses that rule and moves it to `code_fence`.
- Code deleted: the `str(log)` conversion in `log_tail`, and the inline fence rule in `implement_run.py`.

# Design

## Decisions

- **Read the raw response, decode once.** `read_pod_log_text(core, name, namespace, *, tail_lines, **kwargs)` calls `read_namespaced_pod_log` with `_preload_content=False`, joins the chunks of the response and decodes the bytes one time with `bytes.decode("utf-8", errors="replace")`. One decode of the whole body cannot cut a multi-byte character. The function closes the response and gives the connection back.
- **One function, two callers.** `ClusterJobs.log_tail` and the doctor snapshot both read a bounded tail as text. The function lives next to `PodLogStream` in `k8s/service.py`. It takes the `core` API object that each caller already holds, so `log_tail` keeps its own handling of `ApiException` (the status goes into the `ClusterJobError`), and the doctor keeps its request timeout, which it passes through `kwargs`.
- **The text keeps the log as it is.** The function does not split, join or cut lines. The tail is already bounded by `tail_lines`, and the comment keeps only `CONST_ROADMAP_IMPLEMENT_LOG_CHARS` characters.
- **The fake answers as the client does.** For a plain read (`_preload_content` not `False`) the fake returns the escaped text that the client 36.0.3 returns for the bytes the pod wrote. For a raw read it streams the bytes. An answer is the `str` or `bytes` that the pod wrote. A test that reads with the old call then sees the defect, and the test fails before the fix for the real reason.
- **The real client has one test.** A loopback `http.server` serves a log to a real `CoreV1Api`. The test shows the real client gives the right text on the raw path. It does not stub the conversion, so a change in the client shows up.
- **The fence rule has one home.** `roadmap/fence.py` holds `code_fence(text)`: three backticks, or one more than the longest run in the text. The stop comment and the report comment both use it. The text is masked first, so a masked token cannot change the run.
- **The excerpt is cut, then fenced.** The mask runs on the whole decoded text, then the text is stripped and cut to its last `CONST_ROADMAP_IMPLEMENT_LOG_CHARS` characters, then fenced. The cut cannot split a secret that the mask already replaced.
- **No-log text has no fence.** The line `(no log: the Job has no pod)` stays plain text in the comment.

## Rejected alternatives

- **Decode `bytes` in `log_tail`, as the issue says.** The client never returns `bytes` here, so the decode would never run on a real cluster. A test with a fake that returns `bytes` would pass while the comment stayed wrong. Evidence: the probe in the proposal.
- **Undo the repr in `log_tail`** (`ast.literal_eval` of `"b'...'"`, then decode). It repairs one result of the client, not the cause. A log that is valid JSON arrives as the repr of a dict and cannot be undone. The cost of the code and of its edge cases is higher than the raw read.
- **`kubectl logs` through `run_subprocess`.** The Service pod has no `kubectl` in its image, and `KubernetesService` is the seam that the tests fake.
- **`PodLogStream` to read the tail.** It splits the log into lines and cuts a line longer than `DEFAULT_LOG_MAX_LINE_CHARS`. A report that needs the text as written gains nothing from that, and a join would lose the last line break.
- **`KubernetesService.read_pod_logs` in `log_tail`.** It wraps every error in `KubernetesContextError` and drops the HTTP status, which `ClusterJobError` names. The new function lets `ApiException` through, so the existing handling stays.
- **A fence made of `~` characters.** The stop comment uses backticks. One rule is simpler to keep than two.
- **Wait for a client release that fixes the conversion.** The pinned release is the newest, and the source read is unchanged. The raw read is correct with any client version.

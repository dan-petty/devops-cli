# Task: Stream-framing for pod logs (#864)

**Issue**: [#864](https://github.com/dan-petty/devops-cli/issues/864)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: priority/p1-high
**Scope**: type/bug, scope/k8s, scope/argo, scope/ui, priority/p1-high

## Description

Kubernetes pod log streaming previously suffered from line framing and formatting defects across CLI and dashboard consumers:
1. `read_pod_logs` previously set `_preload_content=True` when `follow=False`, causing single-JSON logs (e.g. `{"level": "info"}`) to be parsed through `json.loads` by the client and returned as Python string representations (e.g. `{'level': 'info'}`) rather than raw text.
2. In `follow=True` mode, log chunks were yielded as raw byte chunks without line framing, causing lines split across chunk boundaries (such as `b"a\nb"` and `b"c\n"`) to be printed or buffered as separate entries (`"a"`, `"b"`, `"c"` instead of `"a"`, `"bc"`).
3. Split multi-byte UTF-8 sequences across chunk boundaries caused `UnicodeDecodeError` terminating the stream.
4. CLI consumers (`devops k8s logs` and `devops argo workflows logs`) previously printed without consistent line framing or through console formatters susceptible to Rich markup interpretation or column wrapping.
5. In `devops k8s logs`, errors occurring mid-stream in non-follow mode were previously caught by a broad `except Exception:` that fell back to `kubectl logs`, printing duplicate log tails.

`KubernetesService.read_pod_logs` is updated to return a `PodLogStream` in both follow and non-follow modes using unpreloaded streaming (`_preload_content=False`). Lines are framed incrementally using `codecs.getincrementaldecoder("utf-8")("replace")` splitting strictly on `\n` delimiters. Line lengths are bounded by `DEFAULT_LOG_MAX_LINE_CHARS` (65536) in `src/devops_cli/config/defaults.py`, cutting pending text only when it is strictly longer than the cap so that lines of exact cap length with newlines in subsequent chunks frame without spurious empty lines.

`_execute_legacy_kubectl_logs` catches only initial stream opening failures for kubectl fallback; any error occurring mid-stream raises immediately with its message to prevent swallowed errors and duplicate output. CLI output is written via `write_stdout` with secrets masked and trailing newlines preserved.

### Framer Architecture & Library Selection
Per the acceptance criteria investigation for `io.TextIOWrapper`:
`io.TextIOWrapper.readline(size)` truncates lines of length `cap` before `\n`, returning `cap` characters without `\n` on the first call and then returning `\n` (yielding a spurious empty line `""`) on the subsequent call when `\n` arrives in the next chunk. This violates the invariant that `[b"x" * cap, b"\n"]` must yield exactly one line. In addition, `io.TextIOWrapper` requires an `io.IOBase` implementing `readable()` and `read()`, whereas the Kubernetes client streaming interface operates on `response.stream()`. The small incremental framer using `codecs.getincrementaldecoder` with single-responsibility helpers (`_extract_line`, `_flush_buffer`) was retained to satisfy all framing invariants and bounds safely.

### CLI Formatting Note
`write_stdout` prints through the console writer with `soft_wrap=True` and `markup=False`. As noted in Update 2026-10-08, Rich Console sanitization normalizes control characters and shortcodes; the person-run verification against `kubectl logs` uses a pod whose log has no control characters or `:shortcode:` text.

## Acceptance Criteria

- [x] `read_pod_logs` returns a `PodLogStream` in both modes. Iterating it yields complete lines without their trailing newline. Both modes read the response unpreloaded (`_preload_content=False`) through one decode-and-split path. Pre-1.0, there is no shim: the `str` return goes, and so do the `isinstance(..., str)` branches at `refresh.py:132-133` and `cluster_context.py:329`.
- [x] Offline unit tests in `tests/test_k8s_service.py` with a mocked `CoreV1Api` response:
  - followed chunks `b"a\nb"` and `b"c\n"` yield `["a", "bc"]`;
  - chunks `b"a\n"` and `b"tail"` yield `["a", "tail"]`, so a final partial line is flushed when the stream ends;
  - chunks `b"caf\xc3"` and `b"\xa9\n"` yield `["café"]`;
  - chunk `b"\xff\nok\n"` yields `["\ufffd", "ok"]`, and the stream does not end;
  - a chunk with no newline that is longer than the line cap yields a line of exactly the cap's length, and the rest follows as the next line;
  - pending text is cut only when it is longer than `DEFAULT_LOG_MAX_LINE_CHARS`: a test case `[b"x" * cap, b"\n"]` yields exactly one line;
  - `"a\x0cb\n"` yields one line, because only `\n` ends a line;
  - without follow, a body of `b'{"level": "info"}\n'` yields `['{"level": "info"}']`, and the call passes `follow=False` and `_preload_content=False`.
- [x] The two `close()` tests (`test_k8s_service.py:350-392`) still pass with `["first"]` and `["only"]` in place of `"first\n"` and `"only\n"`. A read blocked on a quiet container still ends when `close()` is called from another thread, and the response is still closed and its connection released.
- [x] `devops argo workflows logs my-wf`: the test's workflow has one `Pod` node, so the loop runs, and the service is mocked.
  - Without `--follow`, a log of `"a\nb\n"` prints exactly `a\nb\n` after the pod header.
  - With `--follow`, chunks `"a\nb"` and `"c\n"` print exactly `a\nbc\n`.
- [x] `devops k8s logs pod-1`, with and without `--follow`, writes each line through `write_stdout` (no Rich markup or wrapping, secrets masked) with exactly one newline after it.
  - Chunks `"a\nb"` and `"c\n"` print `a\nbc\n`.
  - A line containing `[/bold]` prints literally.
  - A 200-character line prints unwrapped.
  - No case calls the kubectl fallback (`run_subprocess` and `_run_cmd` patched and asserted not called).
  - Only a failure to open the native read falls back to kubectl. An error after lines have been written is raised with its message: no swallowed error and no duplicate output. A test covers a mid-body error in non-follow mode.
- [x] Dashboard: a `LogPane` that streams `pod_log_source("web-0", "shop")` reads a mocked `CoreV1Api` response whose chunks are `b"a\nb"` and `b"c\nd\n"`. Its buffer ends with the entries `["a", "bc", "d"]`. The test for the removed `str` branch (`test_ui_reactive.py:1800-1815`) goes.
- [x] Tests never touch the network or a cluster. `uv run devops ci` passes. `changelog.d/864.md` has a `### Fixed` entry.
- Pending a person: on the workstation k3s cluster, pick a pod that has stopped writing, such as a Completed job pod (with no control characters or `:shortcode:` text).
  - `diff <(uv run devops k8s logs <pod> -n <ns> --tail 50) <(kubectl logs <pod> -n <ns> --tail=50)` prints nothing.
  - In `uv run devops dashboard`, opening that pod's logs shows the same lines as `kubectl logs <pod> -n <ns> --tail=100` (the pane's tail is `DEFAULT_LOG_TAIL_LINES`, 100), one row per line, and the status line reads `N retained of N` where N is that line count.

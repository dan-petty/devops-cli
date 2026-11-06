# Design

## Context

The copy of `devops k8s volume move` is one shell pipe of two `kubectl exec` streams through the API server. The destination is slower than the source, so data waits in buffers on the path. When the stdout of the source ends while that data waits, the stream fails with `connection reset by peer`, or the destination gets a short archive with exit 0.

## Decisions

### The source keeps its stdout open until the destination has ended

The source side runs `tar ... -cpf - . && exec cat` with `kubectl exec -i`. `cat` writes nothing, because nothing writes to its stdin, and it keeps the stdout of the remote process open. A named pipe joins the stdout of the destination side to the stdin of the source side. The destination side writes nothing to its stdout, so the pipe carries only its end:

1. GNU tar in `debian:trixie-slim` (1.35) ends the extract at the end-of-archive marker, with its stdin still open.
2. `kubectl exec -i` of the destination ends when its remote process ends, with its stdin still open, and it gives the exit code of that process.
3. The end of that kubectl closes the only writer of the named pipe. kubectl of the source gets the end of its stdin and sends the close over the stream. `cat` ends and the source ends with exit 0.

This rule depends on the destination, so a slow destination needs no longer wait.

### Each failure still fails the copy

- The tar of the source fails: `&&` skips `cat`, the source ends with the code of tar, and the destination gets the end of its stdin and fails with `Unexpected EOF`. `pipefail` gives a code that is not 0.
- The tar of the destination fails: its kubectl ends with the code of tar. `pipefail` gives that code. kubectl of the source ends, on the close of its stdout when it still writes, or on the end of its stdin when it holds.
- A stream of either side stops: that kubectl fails, and the other side ends as above.

The comparison of the digests and the one retry do not change, and the command matches no error text.

### The decisions of the change `2186-volume-move` stay

The copy is still one program that `run_subprocess` starts: bash holds the pipe, and no byte of the copy passes through Python. The command starts no second `subprocess.Popen` child and does not use the exec stream of the Python client. Bash makes the named pipe, so the plan, the dry run and the run show one script, and the dry run makes no file.

Rejected alternatives:

- A fixed wait after the data (`tar ...; sleep 20`). It gave complete copies, but its length has no relation to the speed of the destination, and each copy waits for the full length.
- `tar ... && exec cat >/dev/null` as the hold. It closes the stdout of the remote process when tar ends, while the data still waits on the path, and so it keeps the failure. The Feasibility section of the proposal gives the measure.
- `tar -xpf /dev/stdin` on the destination, which does not drain a stdin that stays open. It is not necessary, because `tar -xpf -` ends at the marker with its stdin open (Feasibility). In the measure it also failed with `Unaligned block in archive`.
- A `coproc` in place of the named pipe. It needs no file, but the script must close the descriptor and collect the two exit codes itself, and `pipefail` does that work for a pipe.
- SPDY in place of WebSocket (`KUBECTL_REMOTE_COMMAND_WEBSOCKETS=false`). The measure of the issue gives fewer complete copies.

## Risks

- A SIGKILL of bash, as the timeout of `run_subprocess` sends, skips the trap, so an empty temporary directory with the named pipe stays on the workstation. It holds no data.
- If a stream stalls with no failure, the copy waits until `DEFAULT_K8S_VOLUME_MOVE_COPY_TIMEOUT_SECONDS`, as it did before this change.

# Proposal

## Why

Issue #3695: `devops k8s volume move` copies with one shell pipe of two `kubectl exec` streams through the API server. The end of the stream can get lost. A live move on 2026-11-05 stopped at the copy step: the copy and its one retry both failed with `connection reset by peer`, and the command undid its steps with no data loss. This blocks the moves of #2147.

The cause: the destination is slower than the source, so data waits in buffers on the path. The source process ends, and its stream closes before that data arrives. The digest comparison stops a short copy that exits 0, so the fault causes a failed move and not a bad copy.

## What Changes

- The source side of the copy keeps its stdout open until the destination side has ended. The source runs `tar ... && exec cat` with `kubectl exec -i`. A named pipe joins the stdout of the destination side to the stdin of the source side. The destination side writes nothing, so the pipe carries only its end.
- The pipe is made in the same bash program that holds the copy, and bash removes it on exit. The command still starts one program through `run_subprocess`, and the plan, the dry run and the run list the same steps.
- The digest comparison and the one retry stay.
- The step 4 text of `k8s/README.md` (Move a volume to another node) states the rule.
- The rule of the copy is observable, so the change has a spec delta: one ADDED requirement of the capability `local-path-volume-placement`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: the copy of a volume move keeps the source open until the destination has ended.

## Impact

- `src/devops_cli/k8s/volume_move.py` (`_copy_argv`), `tests/k8s/test_k8s_volume_move.py`, `k8s/README.md`.
- The cluster: nothing until a person runs a move.

## Feasibility

Measured on 2026-11-05 with temporary pods on the control-plane node (source) and on the worker node with the most free disk (destination), kubectl 1.37.1 and k3s 1.37.2. The data was 100 MiB of random bytes, or a real `tar` of a tree of 3,030 entries and 504 MiB (3,000 small files of up to 64 KiB, 20 files of 1 to 10 MiB, two of 50 MiB, a 200 MiB sparse file, a symbolic link and a directory owned by uid 472). Each copy was compared with the digest script of the command, or with `sha256sum` of the random stream.

Before the change (the issue gives the first three rows; the last rows are from this change):

| Variant | Complete copies |
| :--- | :--- |
| The pipe that the command used | 4 of 8 |
| `KUBECTL_REMOTE_COMMAND_WEBSOCKETS=false` (SPDY) | 3 of 8 |
| The source stays alive 20 s after it sends the data | 8 of 8 |
| Real tar, the pipe that the command used, again | 4 of 5 (one `connection reset by peer`) |

The rule needs three facts about the real tools. Each was checked with commands on the temporary pods:

- GNU tar 1.35 (`tar -xpf -`) ends at the end-of-archive marker with its stdin still open. A local pipe with a writer that stays alive 12 s ended in 0 s. So the destination ends by itself, with no help from the source.
- `kubectl exec -i` ends when the remote process ends, also with its stdin open, and it gives the exit code of the remote process (`exit 7` gave 7 in 0 s). So the end of the destination kubectl is a signal that depends on the destination.
- When the stdin of a `kubectl exec -i` gets its end, the remote process gets the end of its stdin (`cat` ended in 0.4 s). So the source ends after the destination has ended.

Two variants did not work, and the design records why. A hold that closes the stdout of the remote process (`exec cat >/dev/null`) kept the failure: it closed the stream before the data arrived (2 of 3 copies of the real tar and 2 of 2 copies of the random stream failed with `connection reset by peer`). A hold with `tar -xpf /dev/stdin` failed with `Unaligned block`.

The chosen form, through the real `_copy_argv` and `run_subprocess` (the pull request comment holds the numbers):

- 20 of 20 complete copies of the real tar, with equal digests, and 20 of 20 complete copies of the random stream, with equal checksums. In the same session, the plain pipe gave 4 complete copies of 5.
- With the destination pod limited to 200 millicores of CPU, 6 of 6 complete copies of the real tar and 6 of 6 of the random stream. The plain pipe ran once there and was complete, so this run shows that the form works with a slow destination, and does not show a failure of the old form.
- Each failure still fails the copy, and the retry then gives an equal copy: the destination directory missing (tar exit 2), the source directory missing (exit 2), the remote tar of the destination killed (exit 137), the remote tar of the source killed (exit 2, `Unexpected EOF`), the local destination kubectl killed (exit 137), and the local source kubectl killed (exit 2, `Unexpected EOF`). In none of them did the copy end with exit 0, and no temporary directory stayed on the workstation.

## Existing Tool Considered

- `pv-migrate` (v3.7.0). The change `2186-volume-move` rejected it, and the reasons hold: its pod-to-pod strategies need a NetworkPolicy opening in the perimeter, and its `local` strategy uses the same path as this copy.
- `kubectl cp` needs the whole volume on the workstation.
- SPDY in place of WebSocket does not help (3 complete copies of 8).
- A fixed wait after the data (a source that stays alive 20 s) gave 8 complete copies of 8, but its length has no relation to the speed of the destination, and each copy waits for it.
- The fix is a small change to one function of the existing command, which keeps the decisions of `2186-volume-move`: one program through `run_subprocess`, no second `subprocess.Popen` child, no Python client exec stream and no match on error text. The build cost is about 250,000 tokens and 1.5 hours with the measures; keeping it costs nothing more than the command already costs.
- The change deletes no code.

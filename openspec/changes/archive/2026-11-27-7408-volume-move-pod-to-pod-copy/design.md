# Design

## Decisions

- **The destination listens, and the source sends.** bash `/dev/tcp` can only connect, so one side needs Perl. The listener runs where the extract runs, so it can keep the exit code of `tar -x` in a file that the last exec reads.
- **One bash script, four requests.** `copy_argv` keeps its signature and stays one process for `run_subprocess`, so the measure of the copy path runs the same copy, and the retry of the move runs the whole script again. The listen script stops the listener of an earlier copy first.
- **The listener reads to the end of the stream.** GNU tar ends at the end-of-archive marker. The listener then reads the rest of the connection, so the source never gets a reset while it writes the last block.
- **One NetworkPolicy for both copy pods.** It selects the copy pods by their labels and allows ingress and egress among them on port 7373 only. A policy needs both directions: on the k3s of the homelab, an egress rule of the source and an ingress rule of the destination must both allow the traffic.

## Rejected alternatives

- **SPDY in place of WebSocket (`KUBECTL_REMOTE_COMMAND_WEBSOCKETS=false`).** All 633,144,478 bytes arrived, but the pipe did not end within 600 s, and the data still went through the API server two times.
- **A copy Job that runs kubectl in the cluster.** The data would still go through the API server.

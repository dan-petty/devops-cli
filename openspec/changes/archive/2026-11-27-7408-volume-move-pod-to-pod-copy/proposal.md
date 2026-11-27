# Proposal

## Why

`devops k8s volume move` copied the data through two `kubectl exec` streams that a named pipe joined, so the data went from the source node through the API server to the operator's machine and back. On the homelab, the stdout of an exec stream at full speed lost data: a download of 700 MiB from a pod stopped after 13 s with `websocket: close 1006` and 3,985,413 bytes short, and a move of 633 MB stopped two times after about 61 s with `i/o timeout` and undid its steps. An idle exec stream of 150 s and an upload of 700 MiB passed (#7408).

## What Changes

- `copy_argv` returns one bash script of four requests: read the IP address of `<claim>-dst`, start a one-time listener in `<claim>-dst` (Perl `IO::Socket::INET`, port 7373) that gives one connection to `tar -x`, make `<claim>-src` send `tar -c` to that address with bash `/dev/tcp`, and wait for the exit code of the extract. Each exec stream carries only a script and its result.
- The move makes the NetworkPolicy `<claim>-copy` before `<claim>-dst`. It selects the copy pods and allows them ingress from and egress to each other on TCP port 7373 only, so that a namespace that refuses traffic by default lets the copy pass. The move deletes it with the copy pods, the undo deletes it, and the plan refuses it as a leftover.
- The measure of the copy path (`volume_move_measure`) runs the same script.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: the copy of a volume move goes from pod to pod, through a NetworkPolicy of the move.

## Impact

- Code: `src/devops_cli/k8s/volume_move.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Tests: `tests/k8s/test_k8s_volume_move.py`, `tests/k8s/test_k8s_volume_measure.py`
- Documents: `k8s/README.md` (Move a volume to another node), `docs/commands/k8s.md`

## Feasibility

- Measured on the homelab, 2026-11-27, kubectl v1.37.3: the four exec cases above, and a copy by hand from pod to pod of 532 MiB in 7 s (dan-petty/homelab#461).
- The copy image `debian:trixie-slim` holds Perl with `IO::Socket::INET`, bash with `/dev/tcp`, GNU tar and `setsid`; bash cannot listen on a port.
- The homelab k3s enforces NetworkPolicy (kube-router): with a policy that allows nothing, a pod without the copy labels got `Connection refused` from a pod that listened on port 7373.

## Existing Tool Considered

pv-migrate (Apache-2.0) copies between two claims with rsync over SSH from pod to pod, but the move needs its own steps (Argo CD pause, workload stop, compare, rebind), and a second tool would add an install and a second set of copy pods. `kubectl cp` uses the same exec streams. The change replaces the copy script and adds one NetworkPolicy: about 40k tokens and 2 hours.

## Dependencies

None.

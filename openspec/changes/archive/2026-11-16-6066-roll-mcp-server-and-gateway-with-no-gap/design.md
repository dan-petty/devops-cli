# Design

## Decisions
- The MCP server keeps one replica and rolls with `maxSurge: 1` and `maxUnavailable: 0`. The endpoints are stateless, so the old and the new pod can serve at the same time.
- The health route is `GET /healthz` on the FastAPI app, outside the role mounts. It needs no token, because the kubelet holds none. It reads no tool and no setting. The app builds each role server before uvicorn listens, so a 200 tells that the tools are loaded.
- The liveness probe stays a TCP probe. A failed health route takes the pod out of the Service; it does not restart the pod.
- The gateway keeps one replica. The README gives the reason, and a test ties the replica count to a shared cooldown store and a PodDisruptionBudget.

## Rejected alternatives
- Two gateway replicas now: each process would cool a provider on its own failures, and the other replica would still send calls to it.
- A PodDisruptionBudget for one gateway replica: `minAvailable: 1` blocks each drain of the node.
- A health route behind the token: the kubelet sends no token, so the probe would fail.

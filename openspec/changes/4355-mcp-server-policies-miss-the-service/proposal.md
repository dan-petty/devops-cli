# Proposal

## Why

Issue #4355, and the owner decision of 2026-11-10 that `devops-cli-job` pods must reach and use the MCP server. The two NetworkPolicies of the server (`mcp-server-ingress` and `mcp-server-clients`) select the client pods by the label `app.kubernetes.io/name: devops-cli-runner`. `build_job` replaces that label with `devops-cli-job` for every Job of the Service and for `devops k8s run-job`, and the admission policy `roadmap-service-jobs` requires `devops-cli-job`. So no Job pod matches either policy. The default perimeter gives a pod no intra-namespace port, so a Job that calls `/implementation/mcp` would be dropped. Both client switches are off today, so no call fails yet.

## What Changes

- Select `devops-cli-job` in `mcp-server-ingress` (from) and in `mcp-server-clients` (pod selector), in place of `devops-cli-runner`. The rules, the port (TCP 8001) and the peer (the server pods only) stay as they are.
- Add the test `tests/invariants/test_k8s_mcp_server_policies.py`. It fails when the label that the policies admit is not the label that `build_job` sets, and when a policy admits more than TCP 8001 to the server pods.
- Update the comments of both policies, `k8s/README.md` and `SECURITY.md`.

## Capabilities

### New Capabilities

- `mcp-server-network-policies`: which pods may call the MCP server, and on which port.

### Modified Capabilities

None.

## Impact

- `k8s/devops/mcp-server/networkpolicy.yaml`, `k8s/devops/mcp-server/networkpolicy-client.yaml`.
- `tests/invariants/test_k8s_mcp_server_policies.py`, `k8s/README.md`, `SECURITY.md`.
- A Job of the default template (`devops k8s run-job` without `--template runner`) carries the same label, so it can also reach the server. It loads Secret `devops-cli`, as a runner Job does, so it gets no secret that a runner Job lacks.
- Argo CD syncs the policies after the merge. A person turns a client on later (steps in the pull request comment).

## Feasibility

Read on 2026-11-10.

- `_labelled` in `src/devops_cli/k8s/cluster_job.py` sets `app.kubernetes.io/name: devops-cli-job` on the pod template after the labels of the CronJob template. `build_job` is the one builder of runner Jobs.
- The live Job pods (`kubectl -n devops get pods --show-labels`) carry `devops-cli-job`. No live pod carries `devops-cli-runner`. Both CronJobs are suspended (`0 0 1 1 *`), so the template label never reaches a running pod.
- `devops-default-perimeter` has Ingress and Egress in `policyTypes`, no ingress rule, and egress only to DNS, namespace `llm` (4000, 6379), namespace `otel` (4318) and public HTTPS. A pod of namespace `devops` is on none of them. So the egress of a Job pod to the server needs `mcp-server-clients`, and the ingress needs `mcp-server-ingress`. DNS for `mcp-server.devops.svc.cluster.local` already works.
- Credential: the Job pod loads Secret `devops-cli` with `envFrom` (the admission policy allows no other source). The live Secret holds the key names `DEVOPS_CLI_MCP_STAGE_TOKEN` and `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN` (checked by name only, no value was read). #4354 added them.
- The live ConfigMap `devops-cli-config` has no `roadmap.mcp` key yet. A person sets it before turning a client on.

## Existing Tool Considered

NetworkPolicy is the tool. The change builds nothing new: it renames one label value in two policies and adds one invariant test. The LiteLLM gateway can also front MCP servers. That route needs an egress rule from namespace `llm` to namespace `devops` and a gateway MCP configuration, and it is a separate decision. This change stays valid beside it, and that change can remove these policies.

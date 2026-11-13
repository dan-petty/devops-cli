# Design

## Decisions
- **A ConfigMap in the Application `ingress`, beside the Ingress.** The origins follow the hosts of Ingress `llm/open-webui-ingress`. Both are in one Application, and deploy-stack sets the domain in both in one run. A check of the `k8s` row fails when they differ.
- **A ConfigMap, read through `envFrom`.** Helm renders Open WebUI from its values, and git holds no real host. A ConfigMap that Kustomize renders gets the domain through the patches that the hosts use, and Argo CD owns it.
- **Each ConfigMap data value that holds the placeholder.** This is the rule of the environment values (#4542): `_host_fields` names each value that deploy-stack changes, and the gate allows the placeholder only there. No ConfigMap of `devops`, `ingress` or `mattermost` holds the placeholder on `main`, so no other object changes. A ConfigMap key holds only letters, digits, `-`, `_` and `.`, so its JSON pointer needs no escape.
- **The reference is not optional.** With `optional: true`, a pod that starts before Argo CD creates the ConfigMap allows every origin until its next start. Without it, the kubelet holds the container until the ConfigMap exists, and then starts it with the origins.
- **Both Ingress hosts.** Ingress `llm/open-webui-ingress` routes `chat.<domain>` and `homelab.<domain>` to Open WebUI. The Socket.IO server refuses each origin that is not in the list, so a list with `chat.<domain>` only would stop Socket.IO at `homelab.<domain>`.
- **HTTPS only.** Cloudflare serves each host of the tunnel over HTTPS, so the origin of the browser is `https://<host>`.
- **Without Argo CD, the stack `llm` applies the file.** The ConfigMap must exist before the chart installs Open WebUI, and the stack `llm` installs the chart. On a cluster that Argo CD manages, the stacks that set the hosts of `ingress` (`infra`, `devops` and `gitea`) also set the origins.

## Rejected alternatives
- **A Helm value override on the Application `open-webui`, the fix that the issue proposes.** At each sync of `cluster`, Argo CD applies `spec.sources` from git and removes the override (proposal, Feasibility).
- **`CORS_ALLOW_ORIGIN` in `values-open-webui.yaml`.** It needs the real domain in git, and the Argo CD gate refuses the placeholder in a Helm value file.
- **A ConfigMap that deploy-stack applies with `kubectl apply`, outside Argo CD.** No Application owns it (#4542 rejected that for the same reason), and the origins and the hosts are then in two places.
- **A single-source Application `open-webui`, with a wrapper chart in git or Kustomize `helmCharts`.** It changes the chart pin, the image pins, Renovate and the deploy-stack counterpart tests for one value.
- **The Application `ingress` for the stack `llm` too.** `deploy-stack --stack llm` then needs a domain on a cluster that Argo CD manages, and fetches the Application `ingress`, with no gain: the stacks that set the hosts already set the origins.
- **The origins of a NodePort or a port-forward.** Their address changes for each cluster and each run, and a loopback origin lets each local page connect.

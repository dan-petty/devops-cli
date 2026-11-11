# Proposal: #4542

## Why
The cluster start page (Homepage) needs the homelab domain in two container environment values: `HOMEPAGE_VAR_DOMAIN`, which each link uses as `https://<name>.{{HOMEPAGE_VAR_DOMAIN}}/<path>`, and `HOMEPAGE_ALLOWED_HOSTS`, the host check. Git holds only the placeholder domain `example.com` (AGENTS.md rule 10). deploy-stack writes the real hosts as Kustomize patches onto the homelab Applications, but its patch builder reads only Ingress and TLS hosts, IngressRoute `match` and the Mattermost host. A container `env[].value` that holds the placeholder thus stays `example.com` in the cluster. Closes #4542.

## What Changes
- `_host_fields` in `src/devops_cli/k8s/argocd_overrides.py` also returns each `env[].value` of a container or init container of a Deployment that holds the placeholder domain (`holds_template_domain_value`). `host_patches` tests and then replaces each such value, as it does for a host.
- The offline Argo CD gate (`check_argocd_gate`) reads the same fields, so it now allows the placeholder in such a value of a homelab Application. It still refuses the placeholder in each other field of a Deployment.
- `k8s/README.md`, "Homelab Values at Deploy Time", lists the new value and names the Deployment in the paragraph about the patches.

## Capabilities
- Modified: `gitops-host-overrides`. It adds the requirement "deploy-stack sets the configured domain in container environment values".

## Impact
- No object in the three homelab Applications holds such a value today. deploy-stack thus writes the same patches as before on `main`.
- The start page Deployment (a later issue) can put the placeholder in its environment values, and deploy-stack sets the real domain there.
- No new dependency, setting or command.

## Feasibility
- Source read on `origin/main` (5f75d256): `_host_fields` (`src/devops_cli/k8s/argocd_overrides.py:112-137`) reads only the kinds `Ingress`, `IngressRoute` and `Mattermost`. `holds_template_domain_value` (`src/devops_cli/k8s/template.py:69-78`) finds the placeholder and the template variables, and `render_manifest_template` replaces both. `check_argocd_gate` allows the placeholder only at the pointers of `_host_fields` (`src/devops_cli/k8s/argocd_gate.py:169`), so on `main` it refuses a placeholder in an environment value.
- A JSON patch (RFC 6902) `test` and `replace` operation takes any JSON pointer, so `/spec/template/spec/containers/<i>/env/<j>/value` works as the host pointers do. Kustomize applies these patches by `target` (the gate check `tests/gate/k8s_checks/host_overrides.py` builds them for each homelab Application).
- Same patches on `main`: a scratch script rendered `devops`, `ingress` and `mattermost` with `kubectl kustomize` and compared `host_patches` of `origin/main` with this branch. The output was `devops: objects=1 ops=2 same=True`, `ingress: objects=19 ops=46 same=True`, `mattermost: objects=1 ops=2 same=True`.
- The start page study recorded the Homepage variables from the upstream documents (https://gethomepage.dev/installation/, https://gethomepage.dev/configs/kubernetes/).

## Existing Tool Considered
Argo CD and Kustomize have no domain variable for a container environment value. Kustomize `replacements` copies one field or one segment of a field, and does not replace a substring in many values. The existing patch builder is thus extended. Cost: about 150,000 tokens and 2 hours to build, about 5,000 tokens a month to keep, about 30,000 tokens to fix.

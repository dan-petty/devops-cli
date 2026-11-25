---
status: accepted
date: 2026-11-25
decision-makers: [owner]
issue: 4598
body-hash: c6862258d5eb38a2de4d944352247ed2864517dc2ccaceaee498b5f1c3f24392
---

# Homepage is the cluster start page

## Context and Problem Statement

The cluster has about 21 Ingress objects and more service UIs with no Ingress. No page lists the service UIs, so a person must remember each host name. On 2026-11-11, the owner asked for a cluster start page that lists all services.

## Decision Drivers

- Discover service links from Kubernetes Ingress and Traefik IngressRoute annotations without manual list edits.
- Keep configuration in YAML files that Argo CD owns, with the container image pinned by digest.
- Match the warm-neutral design tokens palette (`color: stone`) with no fixed `theme` key so the theme switcher stays active.
- Serve the page at the `start` host of the configured domain through the existing wildcard route and Access application, with no request sent outside the cluster.
- Grant only a read-only ClusterRole (`get` and `list` on namespaces, pods, nodes, ingresses, ingressroutes, and `metrics.k8s.io`) with no Secret access and no write verb.

## Considered Options

- **Homepage**: chosen.
- **A hand-kept link list in a ConfigMap**: rejected, because a person edits it for each service.
- **A hosted page**: rejected, because the page must send no request outside the cluster.

## Decision Outcome

Chosen option: "Homepage", because it discovers links from Ingress and IngressRoute annotations, keeps YAML configuration under Argo CD, and sends no outbound request.

- The start page directory of the environment tree and Application `startpage` of project `homelab` live in dan-petty/homelab, because environment manifests moved out of this repository.
- Homepage uses `color: stone` with no `theme` key, disables update checks, receives the configured domain from `deploy-stack`, and restricts network egress to DNS and the cluster API server with no public egress.

### Consequences

- Good, because new Ingress and IngressRoute annotations appear on the start page with no manual edit.
- Good, because no Secret read, write verb, or public egress crosses a trust boundary.
- Bad, because live deployment, pod security, and network policy checks run against `dan-petty/homelab` on merge there.

### Confirmation

- `tests/invariants/test_adr_records.py` checks this record's front matter, length rules, body hash, and generated index row.
- `devops argo cd apps status startpage` confirms that Application `startpage` is Synced and Healthy after deployment from dan-petty/homelab.

## More Information

- Issue #4598 (and design tokens #4735, #4738, env domain patch #4542).
- Change: `openspec/changes/archive/2026-11-25-4598-deploy-homepage-as-the-cluster-start/`.

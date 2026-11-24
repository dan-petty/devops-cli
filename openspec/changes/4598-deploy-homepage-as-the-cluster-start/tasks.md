# Tasks

## 1. Write the decision record of the start page

Kind: other. Reads: `docs/adr/README.md`, `docs/adr/0036-the-stage-agent-runs-stock-coder-and-publish-checks.md`, `src/devops_cli/roadmap/adr.py`, `src/devops_cli/docs/adr_records.py`, `tests/invariants/test_adr_records.py`. Changes: `docs/adr/0037-homepage-is-the-cluster-start-page.md` (new), `docs/adr/README.md`.

- [ ] 1.1 Write `docs/adr/0037-homepage-is-the-cluster-start-page.md` in the form of `docs/adr/0036-the-stage-agent-runs-stock-coder-and-publish-checks.md` and the template of `docs/adr/README.md`: front matter with `status: accepted`, `date` as the day of the merge, `decision-makers: [owner]`, `issue: 4598` and the `body-hash` that the test prints; the title `Homepage is the cluster start page`; Context and Problem Statement with the 21 Ingress objects, the service UIs with no Ingress and the owner request of 2026-11-11; Decision Drivers for the link discovery, the YAML that Argo CD owns, the digest pin, the colors of the design tokens and the host `start` of the configured domain; Considered Options with Homepage `chosen.`, a hand-kept link list in a ConfigMap `rejected, because` a person edits it for each service, and a hosted page `rejected, because` the page must send no request outside the cluster; Decision Outcome that the start page directory of the environment tree and Application `startpage` of project `homelab` live in dan-petty/homelab, with `color: stone` and no `theme` key; Consequences; Confirmation with `devops argo cd apps status startpage`; and More Information with #4598. Then run `uv run devops docs generate` to write the index table of `docs/adr/README.md`, and set `body-hash` to the value that `uv run devops ci test tests/invariants/test_adr_records.py` prints
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py` passes
- [ ] 1.2 Write `docs/adr/0037-homepage-is-the-cluster-start-page.md` and regenerate the index table of `docs/adr/README.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: `devops argo cd apps status startpage` is Synced and Healthy., Application `startpage` is deployed from dan-petty/homelab, and only a person reads its sync status on the homelab cluster; this repository plans no Application and calls no Argo CD API.
- Pending person: The page loads at the start host through Access., Only a person loads the page through the wildcard Access application, after the pull request of dan-petty/homelab deploys it.
- Pending person: `kubectl -n startpage get deploy homepage -o yaml | grep example.com` prints nothing after deploy-stack., The command reads the live cluster after a deploy-stack run of dan-petty/homelab; this repository deploys no start page.
- Pending person: The pod passes Pod Security `restricted`; the namespace is in `tests/commands/k8s/test_k8s_network_policies.py`., `list_files tests/commands/k8s` listed no such module, and the pod runs from dan-petty/homelab, so a person checks the live pod against Pod Security `restricted`.
- Pending person: The pod sends no request outside the cluster., Only a person watches the traffic of the live pod on the homelab cluster, after the pull request of dan-petty/homelab deploys it.

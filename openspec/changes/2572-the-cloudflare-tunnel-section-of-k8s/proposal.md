# Proposal

## Why

#2572: the Cloudflare tunnel section of k8s/README.md writes hosts as *.homelab.<domain>, but the 24 live Ingress hosts have the form <name>.<domain> with no homelab subdomain. A reader who follows the section configures Cloudflare Access and DNS for a domain that no Ingress serves.

## What Changes

- Rewrite the Cloudflare tunnel section of k8s/README.md to use <name>.<domain> and *.<domain> instead of <name>.homelab.<domain> and *.homelab.<domain>
- Add tests/test_k8s_readme_hosts.py that extracts host tokens from the tunnel section and asserts each matches an Ingress host in k8s/
- The test fails on the current text and passes after the fix
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-api-tunnel`: Tunnel section hosts match Ingress, Offline test guards tunnel hosts

## Impact

- Documents: `k8s/README.md`
- Tests: `tests/test_k8s_readme_hosts.py`

## Feasibility

- The issue cites lines 972, 989-991, 1004 and 1010 of k8s/README.md on origin/main. The context shows the README references hosts like argocd.<domain>, alloy.<domain>, chat.<domain>, qdrant.<domain>, ai.<domain>, and hooks.<domain> in other sections, confirming the <name>.<domain> form is the correct one.
- The Ingress manifests live at k8s/ingress/ingress-routes.yaml and k8s/devops/roadmap-service/ingress.yaml. The issue confirms 24 Ingress hosts with no homelab subdomain.
- The test naming pattern follows existing tests: tests/test_k8s_llm_gateway.py, tests/test_k8s_local_path_placement.py. The new test goes to tests/test_k8s_readme_hosts.py.
- First checks the implementation runs: (1) uv run pytest tests/test_k8s_readme_hosts.py -x to confirm the test fails on the current text; (2) after the fix, the same command exits 0; (3) grep -n 'homelab\.' k8s/README.md to confirm no homelab. host form remains in the tunnel section.

## Existing Tool Considered

None needed. The change is a documentation fix in k8s/README.md and a test over the repository's own Ingress manifests. The written cost is the tokens to edit the tunnel section, write one test file, and fix any test failure, plus the elapsed time of one pull request.

# Tasks

## 1. Write failing test for tunnel section hosts

Reads: none. Changes: `tests/test_k8s_readme_hosts.py`.

- [ ] 1.1 Write tests/test_k8s_readme_hosts.py. The test reads k8s/README.md, locates the Cloudflare tunnel section by its heading, extracts every host-like token (a string matching the pattern of optional asterisk, word characters, hyphens, dots, and the literal <domain>), reads all Ingress manifests under k8s/ to collect the set of host values, then asserts each README host is in the Ingress set or equals *.<domain>. It also asserts no host token contains the substring homelab. The test must fail on the current text because it contains homelab. subdomains, and verify that `uv run pytest tests/test_k8s_readme_hosts.py -x` fails on the base
- [ ] 1.2 Implement the test. Read k8s/README.md as text. Find the section between the Cloudflare tunnel heading and the next same-level heading. Use a regex to extract host-like tokens: tokens that end with <domain> and contain at least one dot before it. Read every YAML file under k8s/ that defines Ingress resources (k8s/ingress/ingress-routes.yaml, k8s/devops/roadmap-service/ingress.yaml, and any other Ingress manifest). Collect the set of host values from the spec.rules[].host fields. For each README host token, assert it is in the Ingress host set or equals *.<domain>. Assert no token contains the substring homelab. Use pytest.fail with a message naming each mismatched host, and verify that `uv run pytest tests/test_k8s_readme_hosts.py -x` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Fix tunnel section host names in README

Reads: none. Changes: `k8s/README.md`.

- [ ] 2.1 The test tests/test_k8s_readme_hosts.py from the previous group must pass after the fix. Run uv run pytest tests/test_k8s_readme_hosts.py -x and confirm exit code 0, and verify that `uv run pytest tests/test_k8s_readme_hosts.py -x` fails on the base
- [ ] 2.2 In the Cloudflare tunnel section of k8s/README.md, replace every occurrence of *.homelab.<domain> with *.<domain>. Replace every occurrence of <name>.homelab.<domain> with <name>.<domain> for each named host (chat, grafana, ai, argocd, git, hooks, k8s, alloy, qdrant, prometheus). Verify each named host appears in k8s/ingress/ingress-routes.yaml or k8s/devops/roadmap-service/ingress.yaml. Remove any sentence that references the homelab subdomain as a DNS wildcard target, and verify that `uv run pytest tests/test_k8s_readme_hosts.py -x` passes
- [ ] 2.3 k8s/README.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

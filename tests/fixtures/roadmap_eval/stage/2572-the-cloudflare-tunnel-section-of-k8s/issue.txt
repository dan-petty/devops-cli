## Problem or Motivation

The Cloudflare tunnel section of `k8s/README.md` writes the public hosts as `*.homelab.<domain>` (lines 972, 989-991, 1004 and 1010 on origin/main, 2026-10-29). The live cluster serves 24 Ingress hosts, and none of them has `.homelab.` in its name: each one has the form `<name>.<domain>`. A person who follows the section sets the Cloudflare Access application and the DNS wildcard to a domain that no Ingress serves.

Found while #1648 confirmed `k8s/README.md` against the live cluster (read-only `kubectl get ingress -A`). #1648 kept to its own sections and did not change this one.

## Proposed Solution & Architectural Design

- Write the hosts in the tunnel section as `<name>.<domain>`, the form the Ingress manifests use, and check each named host against `k8s/` (for example `chat`, `grafana`, `ai`, `argocd`, `git`).
- Check the Access application and DNS steps against the current Cloudflare setup that `devops cloudflare` and the tunnel manifests use.
- Add an offline test that each host the README names in that section matches an Ingress host pattern in `k8s/`, so the text cannot drift again.

## Target Subsystem

`k8s/README.md`, Cloudflare tunnel section.

## Existing Tool Considered

None needed: a documentation fix and a test over the repository's own manifests.

## Acceptance criteria

- No `homelab.<domain>` host form remains in `k8s/README.md` unless an Ingress in `k8s/` uses it.
- The test fails on the current text and passes after the fix.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=9e8317bb778264500aa5ae8ce3f7351ed19c30e4 -->
## Proposed design

### Problem statement
The Cloudflare tunnel section of k8s/README.md names public hosts as *.homelab. and individual hosts as .homelab.. The live Ingress manifests use . with no homelab subdomain. A person who follows the section sets the Cloudflare Access application and the DNS wildcard to a domain that no Ingress serves.

### Acceptance criteria

### Requirement: Host form matches Ingress
The Cloudflare tunnel section of k8s/README.md SHALL name each host in the form . and the wildcard as *., matching the Ingress manifests in k8s/.

#### Scenario: No homelab subdomain remains
- **WHEN** the text of the Cloudflare tunnel section is scanned for the substring homelab.
- **THEN** no host pattern in that section contains the substring homelab.

### Requirement: Offline test guards the hosts
An offline test SHALL verify that every host named in the Cloudflare tunnel section of k8s/README.md matches an Ingress host defined in k8s/.

#### Scenario: Test fails on broken text
- **WHEN** the test runs against the README before the host names are corrected
- **THEN** the test exits with a non-zero code and names each host that does not match an Ingress.

### Requirement: Test passes after fix
The offline test SHALL pass after the host names in the tunnel section are corrected to the Ingress form.

#### Scenario: Test passes on corrected text
- **WHEN** the test runs against the README after the host names are corrected
- **THEN** the test exits with code 0.

### Existing Tool Considered
No check has run. No external tool is needed. This is a documentation fix in k8s/README.md and a test over the repository's own Ingress manifests. The written cost is the tokens to edit the tunnel section, write one test file, and fix any test failure, plus the elapsed time of one pull request.

### Key questions
- **What is the correct host pattern that the Ingress manifests use?**: Each Ingress host is . with no homelab subdomain. The names in use are chat, ai, grafana, argocd, git, hooks, k8s, alloy, qdrant, and prometheus. The wildcard DNS record is *.. [sources: k8s/README.md, k8s/ingress/ingress-routes.yaml]
- **What is the correct wildcard form for the Cloudflare Access application and DNS record?**: The wildcard is *., not *.homelab.. The Gitea section of the README and the devops cloudflare access sync command both use *.. [sources: k8s/README.md]
- **Where does the offline test live?**: tests/test_k8s_readme_hosts.py, following the naming pattern of the other k8s tests such as tests/test_k8s_llm_gateway.py and tests/test_k8s_local_path_placement.py. (best practice) [sources: tests/test_k8s_llm_gateway.py, tests/test_k8s_local_path_placement.py]
  - Chosen: tests/test_k8s_readme_hosts.py. Follows the existing test naming pattern for k8s-related tests in the tests/ directory.
  - Rejected: k8s/tests/test_readme_hosts.py. No existing test directory under k8s/. The project keeps all tests in tests/.
- **What does the test check?**: The test extracts every host-like token from the Cloudflare tunnel section of k8s/README.md, then checks that each one matches a host defined in an Ingress manifest under k8s/. It also checks that the wildcard form is *. and not *.homelab.. (best practice) [sources: k8s/ingress/ingress-routes.yaml, k8s/devops/roadmap-service/ingress.yaml]
  - Chosen: Extract hosts from the section and match each against Ingress manifests. Catches any host that does not match, not only the homelab. form. More robust against future drift.
  - Rejected: Assert only that the substring homelab. is absent. Simpler, but misses a host that uses a different wrong form.

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "refine.alternatives_asked": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "67c64c76b230ac961d587266e4c7c6257fff163867cdbcd5578bb244c337646a", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "025d883a40de952a3c009b7f0981c9b232b28e35cc2e01aea474873c8055e2b2", "stage.branch": "docs/2572-the-cloudflare-tunnel-section-of-k8s", "stage.file_cap": null, "stage.groups": "[[\"Write failing test for tunnel section hosts\", 3657], [\"Fix tunnel section host names in README\", 3542]]", "stage.needs_split": null, "stage.pr": "2999", "stage.ready": "2999", "stage.sha": "bd043ae8d7344ad8a3ac792e0c3ce526853f307c"} -->

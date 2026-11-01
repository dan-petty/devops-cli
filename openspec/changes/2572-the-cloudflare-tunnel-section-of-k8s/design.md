# Design

## Decisions

- **Place the test at tests/test_k8s_readme_hosts.py**: Follows the existing naming pattern of tests/test_k8s_llm_gateway.py and tests/test_k8s_local_path_placement.py. The project keeps all tests in tests/.
- **Extract and match every host token against Ingress manifests, not just check for the homelab. substring**: Catches any host that does not match an Ingress, not only the homelab. form. More robust against future drift where a different wrong subdomain is introduced.
- **The test reads Ingress manifests from k8s/ rather than hardcoding the expected host list**: If a new Ingress is added, the test still passes without editing the test. If a host is removed from Ingress, the test fails and names the stale README reference.

## Rejected alternatives

- **Place the test at k8s/tests/test_readme_hosts.py**: No existing test directory under k8s/. The project keeps all tests in tests/.
- **Assert only that the substring homelab. is absent from the tunnel section**: Simpler, but misses a host that uses a different wrong subdomain form. The issue asks for a guard against any drift, not just the current error.

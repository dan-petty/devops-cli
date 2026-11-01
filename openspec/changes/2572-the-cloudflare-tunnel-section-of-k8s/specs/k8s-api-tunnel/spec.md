## ADDED Requirements

### Requirement: Tunnel section hosts match Ingress
The Cloudflare tunnel section of k8s/README.md SHALL name each host in the form <name>.<domain> and the wildcard as *.<domain>, matching the Ingress manifests in k8s/.

#### Scenario: No homelab subdomain remains
- **WHEN** the text of the Cloudflare tunnel section is scanned for the substring homelab.
- **THEN** no host pattern in that section contains the substring homelab.

### Requirement: Offline test guards tunnel hosts
An offline test SHALL verify that every host named in the Cloudflare tunnel section of k8s/README.md matches an Ingress host defined in k8s/.

#### Scenario: Test fails on broken text
- **WHEN** the test runs against the README before the host names are corrected
- **THEN** the test exits with a non-zero code and names each host that does not match an Ingress.

#### Scenario: Test passes on corrected text
- **WHEN** the test runs against the README after the host names are corrected
- **THEN** the test exits with code 0.

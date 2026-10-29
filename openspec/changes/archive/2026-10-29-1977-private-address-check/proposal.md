# Proposal

## Why

Issue #1977: SECURITY.md rule 8 forbids an RFC 1918 address and an internal `.lan` host in a committed file, but no check holds the rule. Only `detect-private-key` and review guard the tree.

## What Changes

- A new invariant test, `tests/invariants/test_committed_addresses.py`, reads each file that git tracks. It splits each file into the runs of characters that an address or a host name can hold, parses each run with `ipaddress`, and fails on an RFC 1918 host address or a `.lan` host. No pattern matches an octet.
- **Allowed:** a range in CIDR form with a prefix shorter than 32, because a range names no machine (network policy `except` lists, VPC and subnet CIDRs). Also allowed: three upstream values that the test names, each with its source (minikube's docker-driver node address, AKS's default DNS service address, the OpenTelemetry example of `server.address`).
- **Out of scope:** test code (`tests/**/*.py`, `.ast-grep/rule-tests/`), because the egress and reference classifiers need private addresses as test input; the archived OpenSpec changes, which record merged work; and `CHANGELOG.md`, which release-please writes.
- **Fixed:** the living specs `configured-service-urls` and `stack-credential-sync` use `192.0.2.10` in place of the RFC 1918 address they named, as the same spec's other scenarios do, and the five tests that feed those scenarios send the same address. A docstring in `security/reference_extractor.py` uses the NAT64 form of `192.0.2.1`.
- SECURITY.md rule 8 names the check.
- The spec text changes, so the change carries MODIFIED deltas. The check itself is a test, which carries no delta.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `configured-service-urls`: three requirements use an RFC 5737 address in their scenarios.
- `stack-credential-sync`: one requirement uses an RFC 5737 address in its scenarios.

## Impact

- `tests/invariants/test_committed_addresses.py` (new), `tests/test_argo.py`, `tests/test_grafana.py`, `tests/test_k8s_credentials.py`, `tests/test_prometheus.py`, `tests/test_http_egress.py`.
- `src/devops_cli/security/reference_extractor.py` (docstring).
- `openspec/specs/configured-service-urls/spec.md`, `openspec/specs/stack-credential-sync/spec.md`, `SECURITY.md`.

## Feasibility

Measured on origin/main 40116804 with the new scan, by scope and kind (values not shown):

| Scope | RFC 1918 host addresses | Ranges | Upstream values | `.lan` hosts |
| :--- | ---: | ---: | ---: | ---: |
| In scope | 10 in 3 files (fixed) | 26 in 12 files | 6 in 4 files | 0 |
| Test code | 98 in 27 files | 25 | 9 | 4 in 4 files |
| Archived OpenSpec changes | 14 in 4 files | 0 | 0 | 0 |
| `CHANGELOG.md` | 1 | 1 | 0 | 0 |

- The issue's first criterion, "the test reads every git-tracked text file", does not hold as written. The egress tests and the reference-extractor tests must send an RFC 1918 address: `CONST_PRIVATE_NETWORKS` and `security/reference_extractor.py` treat RFC 1918 space apart from the RFC 5737 documentation blocks. Release-please owns `CHANGELOG.md`, and nobody edits it by hand. An archived change records merged work. The owner rule of 2026-10-20 (a check that does not apply is not run there) gives the scope.
- `ipaddress` 3.14 reads the RFC 5737 blocks as `is_private`, so the test checks membership of RFC 1918's three blocks, not `is_private`.
- `http/egress.py` refuses `192.0.2.10` at the public and loopback levels and admits it at the private level, as it does `10.0.0.1`. The five changed tests pass with the new address (279 tests in their files).
- The whole scan takes 0.78 s on this host.

## Existing Tool Considered

- Python's `ipaddress` parses and classifies each address. The test adds no address pattern.
- Gitleaks 8.30.1 is pinned in `tools.lock`, but its custom rules match text with regular expressions, so they cannot parse an address or tell a range from a host. No CI job runs Gitleaks on the tree today. A Gitleaks rule would add a CI step and a regular expression for octets, which the issue rules out.
- The change deletes no code. Its cost is one test module of about 170 lines.

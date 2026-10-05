# Task: Egress Guards Refuse Cloud Metadata (#897)

**Issue**: [#897](https://github.com/dan-petty/devops-cli/issues/897)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/security

## Description

Refactor egress guards to refuse cloud metadata in every numeric, NAT64, and provider form, classified by `ipaddress` and maintained network safety classifiers rather than brittle ad-hoc string matching.
- Add `dnspython==2.8.0` direct dependency for deterministic DNS name syntax and relative label parsing.
- Refactor `is_cloud_metadata_host` to leverage `pydantic_ai._ssrf` network classifiers, dynamically derived link-local networks (`169.254.0.0/16`, `fe80::/10`), numeric host parsing via `httpx2.URL` and `socket.AI_NUMERICHOST`, and `dns.name.from_text` syntax parsing (failing closed on `DNSException`).
- Refactor `is_loopback_host` to deterministically recognize loopback IP addresses (IPv4, IPv6, IPv4-mapped `::ffff:127.0.0.1`), numeric forms, and `localhost` without DNS queries.
- Refactor `is_non_public_ip` to inspect global reachability across single addresses and networks.
- Refactor `validate_url` and `validate_url_egress` to enforce metadata refusals ahead of `allow_private` checks, check resolved DNS IPs against metadata classifiers, and enforce syntax validation.
- Remove forbidden ad-hoc prefix/subset matching across `src/` (`CONST_CLOUD_METADATA_HOSTS`, `CONST_CLOUD_METADATA_IPS`, `CONST_LOCAL_HOSTNAMES`, `_LOOPBACK_AND_LOCAL_HOSTS`, `_ALLOWED_LOCAL_HOSTS`, `startswith("169.254.")`, `strip("[]")`).
- Update callers in `ai/mcp/server.py`, `ai/spend/pricing.py`, `commands/k8s/networking.py`, `cloudflare/client.py`, and `sandbox/models.py`.

## Acceptance Criteria

- [x] Egress guards refuse IPv4 link-local (`169.254.0.0/16`), IPv6 link-local (`fe80::/10`), NAT64 metadata (`64:ff9b::169.254.169.254`), 6to4, Teredo, dword/hex/octal representations, fullwidth dot encodings, and provider metadata hostnames.
- [x] All classification uses `ipaddress` and `pydantic_ai._ssrf` without ad-hoc string prefixing or partial keyword subsets.
- [x] `is_loopback_host` recognizes `localhost`, `127.0.0.1`, `::1`, `127.0.0.2`, `::ffff:127.0.0.1`, `LOCALHOST.` without DNS resolution.
- [x] `_normalize_ip_cidr` rejects scoped IP addresses (`fe80::1%eth0/128`) and normalizes case.
- [x] Fast in-gate checks pass and `changelog.d/897.md` is provided.
- Pending a person: `uv run devops ci` passes on this branch.

## Deliverables

- [x] `pyproject.toml` and `uv.lock`: added `dnspython==2.8.0`.
- [x] `src/devops_cli/config/constants.py`: updated metadata host constants.
- [x] `src/devops_cli/core/validation.py`: hardened `is_cloud_metadata_host`, `is_loopback_host`, `is_non_public_ip`, and egress URL validation.
- [x] `src/devops_cli/ai/mcp/server.py`: use `is_loopback_host` for SSE binding checks.
- [x] `src/devops_cli/ai/spend/pricing.py`: use `is_loopback_host` for local pricing.
- [x] `src/devops_cli/commands/k8s/networking.py`: use `is_loopback_host` for host preservation.
- [x] `src/devops_cli/cloudflare/client.py`: robust CIDR normalization and scope-id rejection.
- [x] `src/devops_cli/sandbox/models.py`: clean exception handling during host resolution.
- [x] `src/devops_cli/sandbox/metrics.py`: use `is_loopback_host`.
- [x] `changelog.d/897.md`: changelog fragment.
- [x] `docs/agent/tasks/task-897-egress-guards-cloud-metadata.md`: task tracking file.
- Extraction from file reference scanner: moved to #1174.

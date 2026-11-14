# Tasks

## 1. Accept a public IPv6 whitelist entry

Reads: `src/devops_cli/sandbox/models.py`, `tests/sandbox/test_sandbox_network_config.py`, `tests/commands/test_sandbox_network_policy.py`. Changes: the same files.

- [ ] 1.1 In `_validate_public_whitelist_item`, parse the host with `ipaddress.ip_network(host, strict=False)`; refuse a metadata or non-public network; call `is_loopback_or_private_host` only for a name.
  - Verification: `$ uv run devops ci test tests/sandbox/test_sandbox_network_config.py` passes
- [ ] 1.2 Add tests for a public IPv6 CIDR, a CIDR with host bits, a bare address, four non-public IPv6 literals, a name with no lookup, and the command.
  - Verification: `$ uv run devops ci test tests/commands/test_sandbox_network_policy.py tests/sandbox/test_sandbox_network_config.py` passes

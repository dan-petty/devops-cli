# Proposal

## Why

The issue #2184 removes a hand-kept copy of pydantic-ai's private non-public blocks. The copy can drift from upstream and hides the owner's rule that changes use maintained libraries.

## What Changes

- Replace the hand-kept non-public block list in `src/devops_cli/core/validation.py` with Python's `ipaddress` properties.
- Keep the ISATAP and IPv4-compatible rules with RFC comments and tests.
- Delete the copied block-list constants from `src/devops_cli/config/constants.py`.
- Add a table test in `tests/test_validation_non_public.py` for the IANA registries and the transition forms.
- Add a spec delta to `public-api-egress` for the maintained classification source.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `public-api-egress`: Non-public address classification uses maintained sources

## Impact

- Code: `src/devops_cli/core/validation.py`, `src/devops_cli/config/constants.py`
- Tests: `tests/test_validation_non_public.py`

## Feasibility

- The inputs show the premise: `src/devops_cli/core/validation.py` imports `CONST_PRIVATE_NETWORKS` and the transition constants from `src/devops_cli/config/constants.py`, and its `is_non_public_ip` docstring names pydantic-ai's non-public blocks.
- The implementation first runs `uv run python -c "import importlib.util; print(importlib.util.find_spec('pydantic_ai._ssrf'))"` to confirm the private module.
- It then runs `uv run python -c "import ipaddress; print(ipaddress.ip_address('192.0.2.1').is_global, ipaddress.ip_address('64:ff9b::c000:201').is_global)"` to confirm the standard-library answers.
- It runs `uv run devops ci test tests/test_validation_non_public.py` after the table test is written.
- The issue depends on #2152, which changes `parse_numeric_ip` in the same module. This plan assumes #2152 is merged first.

## Existing Tool Considered

Python's standard library `ipaddress` is the open, maintained source. It covers `is_global`, `ipv4_mapped`, `sixtofour` and `teredo`. The change keeps two small rules for ISATAP (RFC 4214) and IPv4-compatible forms (RFC 4291). Those rules cost about 80 lines, 1,200 tokens to build, 200 tokens a year to keep, 400 tokens for each correction, and about 2 hours. The change deletes `CONST_PRIVATE_NETWORKS`, `CONST_NAT64_PREFIXES`, `CONST_TEREDO_PREFIX`, `CONST_IPV4_EMBEDDING_IPV6_PREFIXES`, `CONST_ALL_EMBEDDED_OFFSETS`, `_non_public_networks`, `_exhaustive_embedded_ipv4s`, `_standard_embedded_ipv4s` and `_embedded_ipv4s`.

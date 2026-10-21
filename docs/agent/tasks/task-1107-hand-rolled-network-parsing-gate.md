# Task: Hand-rolled network parsing fails devops ci, AGENTS.md makes the library the rule, and reviews stop discarding the findings (#1107)

**Issue**: [#1107](https://github.com/dan-petty/devops-cli/issues/1107)
**Scope**: scope/ci, scope/review
**Feasibility**: Verified against `ast-grep-cli==0.51.0` on Python 3.14. ast-grep scans the source tree in ~0.3s without telemetry or network egress. Ruff TID251 bans legacy `socket.inet_*` APIs.

## Description

Enforces standard library parsers (`ipaddress`, `urllib.parse`, `httpx2.URL`, `dns.name`) across the codebase instead of hand-rolled string splitting, regexes, port tables, or bracket stripping. Bypasses are prevented with architectural meta-tests and pre-commit hooks with a ceiling of 0 suppressions.

Delivered across 5 incremental pull requests.

## Deliverables

### PR 1: Core Gate, TID251, Meta-Test, and First Three Rules (Part of #1107)

- [x] Add `ast-grep-cli==0.51.0` to `dev` dependency group in `pyproject.toml` and lock with `uv lock`.
- [x] Configure Ruff `TID251` (banned-api) in `pyproject.toml` banning `socket.inet_aton`, `socket.inet_ntoa`, `socket.inet_pton`, and `socket.inet_ntop` with message `"Parse and format addresses with ipaddress.ip_address."`.
- [x] Add `"flake8-tidy-imports"` to `CONST_RUFF_LINT_KEYS` in `src/devops_cli/config/constants.py`.
- [x] Define root `sgconfig.yml` pointing to `.ast-grep/rules` and `.ast-grep/rule-tests`.
- [x] Add first 3 `net-*` rules to `.ast-grep/rules/` and unit tests to `.ast-grep/rule-tests/`:
  - `net-cidr-build`: flags CIDR text formatting like `f"{ip}/32"`.
  - `net-port-table`: flags default-port branching `443 if ... else 80`.
  - `net-ip-literal`: flags direct comparison with IP literals without `ipaddress.ip_address`.
- [x] Remediate existing construct sites in `src/`:
  - `src/devops_cli/core/validation.py`: replace default port table with `httpx2.URL(url).origin.port`.
  - `src/devops_cli/core/validation.py`: parse legacy IPv4 numbers without banned `socket.inet_aton`.
  - `src/devops_cli/security/sanitizer.py`: replace loopback list check with `is_loopback_host(host)`.
- [x] Register `CONST_NET_CONSTRUCT_RULES`, `CONST_AST_GREP_SCAN_ARGS`, and `CONST_BANNED_HAND_ROLLED_APIS` in `src/devops_cli/config/constants.py`.
- [x] Add `constructs` check row to `get_check_specs()` in `src/devops_cli/commands/ci.py`.
- [x] Add `ast-grep-scan` and `ast-grep-test` hooks to `.pre-commit-config.yaml`.
- [x] Add meta-test `test_the_network_construct_gate_has_no_escape` and escape tests `test_every_network_construct_escape_is_reported` in `tests/test_architectural_invariants.py`.
- [x] Add `tests/test_net_construct_rules.py` covering rule tests, scanner detection, TID251, and constants.

### Follow-up Pull Requests

- PR 2: AGENTS.md, template, `generate_agents.md`, `architecture.md` instruction updates and `.devops/review.md` house rule under #1107.
- PR 3: `net-address-list` rule and TLS defaults holding `ipaddress` objects under #1107.
- PR 4: `net-scheme-in`, `net-scheme-affix`, `net-url-build`, `net-bracket-affix` under #1107.
- PR 5: `net-domain-suffix`, `net-domain-list`, `net-normalise`, `net-hostport` under #1107 (closes #1107).

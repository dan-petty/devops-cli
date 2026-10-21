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

### PR 3: `net-address-list` Rule and TLS Defaults Holding `ipaddress` Objects (Part of #1107)

- [x] Add `net-address-list` rule to `.ast-grep/rules/net-address-list.yml` and test cases to `.ast-grep/rule-tests/net-address-list-test.yml`.
- [x] Register `"net-address-list"` in `CONST_NET_CONSTRUCT_RULES` in `src/devops_cli/config/constants.py`.
- [x] Migrate `DEFAULT_HOMELAB_IPS` in `src/devops_cli/config/defaults.py` and `CertGenerationRequest.sans` in `src/devops_cli/models/tls.py` to hold `ipaddress` objects.
- [x] Update TLS consumers in `src/devops_cli/crypto/tls_certificates.py` (`_build_san_extension`, `generate_server_certificate`, `generate_homelab_stack_certificates`) and `src/devops_cli/commands/tls.py` to preserve certificate content and string JSON serialization.
- [x] Remediate literal scheme tuples across the codebase with `urllib.parse.urlsplit(value).scheme`:
  - `src/devops_cli/ai/agents/tools.py`: MCP toolset URL target scheme check.
  - `src/devops_cli/ai/research/edges.py`: markdown href scheme filtering.
  - `src/devops_cli/ai/review/samples.py`: sample repository HTTPS/file validation.
  - `src/devops_cli/commands/ai_ingest.py`: remote documentation URL check.
  - `src/devops_cli/commands/k8s/networking.py`: minikube service URL extraction.
  - `src/devops_cli/ai/kb.py`: knowledge base article sources validation.
- [x] Add unit tests for case-insensitive scheme matching (`HTTPS://`) and non-URLs, TLS SAN `x509.IPAddress` generation, string JSON output, and `net-address-list` ast-grep scanner detection.

### PR 4: Scheme, URL Authority, and IPv6 Bracket ast-grep Rules (Part of #1107)

- [x] Add `jeepney==0.9.0` to dependencies in `pyproject.toml` and lock with `uv lock`.
- [x] Add 4 `net-*` rules to `.ast-grep/rules/` and unit tests to `.ast-grep/rule-tests/`:
  - `net-scheme-in`: flags substring tests `"://" in x` or `not in x`.
  - `net-scheme-affix`: flags prefix/suffix tests on schemes, unix sockets, or IPv4 prefixes.
  - `net-bracket-affix`: flags hand-rolled IPv6 bracket parsing with `startswith("[")` and `":" in host`.
  - `net-url-build`: flags building URL authorities using f-strings instead of `httpx2.URL`.
- [x] Register `"net-bracket-affix"`, `"net-scheme-affix"`, `"net-scheme-in"`, and `"net-url-build"` in `CONST_NET_CONSTRUCT_RULES` in `src/devops_cli/config/constants.py`.
- [x] Add `CONST_VALKEY_SCHEMES` to `src/devops_cli/config/constants.py`.
- [x] Remediate hand-rolled scheme, URL authority, and bracket parsing across `src/`:
  - `src/devops_cli/valkey/client.py`: parse Valkey and Redis endpoints using `urllib.parse.urlsplit`.
  - `src/devops_cli/config/settings.py`: parse and normalize Valkey URLs and hosts using `urllib.parse.urlsplit`.
  - `src/devops_cli/commands/devcontainer.py`: parse `DBUS_SESSION_BUS_ADDRESS` using `jeepney.bus.parse_addresses`.
  - `src/devops_cli/commands/ai_gateway.py`: construct gateway URL authority with `httpx2.URL(scheme="http", host=host, port=port)`.
  - `src/devops_cli/commands/ai_runs.py`: construct Valkey run index URL with `httpx2.URL(scheme="valkey", host=host, port=port)`.
  - `src/devops_cli/commands/k8s/cluster_context.py`: check manifest path scheme with `bool(urlsplit(path).scheme)`.
  - `src/devops_cli/commands/repos.py`: extract URL path and file scheme using `urllib.parse.urlsplit`.
  - `src/devops_cli/commands/sandbox.py`: check target schemes with `bool(urlsplit(identifier).scheme)`.
  - `src/devops_cli/core/paths.py`: check absolute path schemes with `bool(urlsplit(unquoted).scheme)`.
  - `src/devops_cli/k8s/argocd_gate.py`: normalize git URLs with `urllib.parse.urlsplit`.
  - `src/devops_cli/roadmap/refine.py`: check HTTP/HTTPS source schemes with `urlsplit(src).scheme in {"http", "https"}`.
  - `src/devops_cli/security/reference_extractor.py`: validate URL targets using `urllib.parse.urlsplit` without substring checks.
  - `src/devops_cli/ai/agents/media.py`: check media URI scheme with `urlsplit(data).scheme == "media+sha256"`.
- [x] Add unit tests for IPv6 host parsing and upper-case schemes in Valkey endpoint and config parsers, IPv6 bracketing in gateway and run store URL builders, `DBUS_SESSION_BUS_ADDRESS` parsing with escaped paths and multiple addresses through `jeepney`, and ast-grep scanner detection for each new rule.

### PR 5: Domain and Hostport Rules and Gate Completion (Closes #1107)

- [x] Add 4 `net-*` rules to `.ast-grep/rules/` and unit tests to `.ast-grep/rule-tests/`:
  - `net-domain-suffix`: flags domain matching by string suffix with `endswith` or `removesuffix`.
  - `net-domain-list`: flags literal assignment lists of domain suffixes.
  - `net-normalise`: flags hand-rolled host canonicalisation via `.strip("[]")` or `.lower().rstrip(".")`.
  - `net-hostport`: flags host, port, or userinfo splitting by hand with `:|@` and `split|rsplit|partition|rpartition`.
- [x] Register `"net-domain-list"`, `"net-domain-suffix"`, `"net-hostport"`, and `"net-normalise"` in `CONST_NET_CONSTRUCT_RULES` in `src/devops_cli/config/constants.py` (completing all 12 rules).
- [x] Remediate hand-rolled domain suffix and normalization sites across `src/`:
  - `src/devops_cli/ai/models/ollama.py`: replace `.endswith(".ollama.com")` with `dns.name.is_subdomain`.
  - `src/devops_cli/commands/review.py`: replace `.endswith(".svc.cluster.local")` with `dns.name.is_subdomain`.
  - `src/devops_cli/k8s/template.py`: normalize domain using `dns.name.from_text` and `to_unicode(omit_final_dot=True)`.
  - `src/devops_cli/http/urls.py`: replace `netloc.split("@")` with `netloc.endswith(":")`.
  - `src/devops_cli/commands/k8s/networking.py`: parse `existing_host_raw` using `urlsplit`.
  - `src/devops_cli/ai/spend/pricing.py`: canonicalize `host` using `urlsplit(f"//{host}").hostname` without `strip("[]")`.
  - `src/devops_cli/core/validation.py`: canonicalize hosts in `is_loopback_host` and `is_loopback_or_private_host` using `urlsplit` and `dns.name.from_text(h).to_text(omit_final_dot=True)`.
- [x] Add unit tests for mixed-case, trailing dots, look-alikes (`evilollama.com`), bracketed IPv6, and scanner detection for each of the 4 new rules in `tests/test_net_construct_rules.py`.
- [x] Zero ast-grep scan errors and zero suppressions across all 12 rules in `src/`.
- [x] Add `changelog.d/1107.md`.

### Follow-up Tracking

- PR 2: AGENTS.md character budget ceiling (#1107 Comment 4) paused; tracked for budget refactor.

# Task: Local Names from the Public Suffix List and DNS-Label Domain Matching (#887)

**Issue**: [#887](https://github.com/dan-petty/devops-cli/issues/887)
**Status**: Done
**Feasibility**: Verified against `tldextract` 5.3.2 (`TLDExtract(suffix_list_urls=(), fallback_to_snapshot=True, cache_dir=None)`) and `dnspython[idna]` 2.8.0 (`dns.name.from_unicode(..., idna_codec=dns.name.IDNA_2008)`, `Name.is_subdomain`) in the local environment.

## Summary

Replaced scattered hand-written domain suffix lists and `.endswith(...)` substring checks across egress validation, Kubernetes URL configuration, AI spend pricing, `web_fetch`, `PlaywrightBrowser.navigate`, and sandbox local whitelisting with a shared offline Public Suffix List (PSL) classifier and IDNA-2008 DNS-label comparison module (`src/devops_cli/core/dns_names.py`).

## Deliverables

- [x] Created `src/devops_cli/core/dns_names.py` with lazy imports of `tldextract` and `dns.name`, a shared cache-less `get_tld_extractor()`, `is_public_dns_name(host)` (rejecting IP literals, malformed labels, bare suffixes, and RFC 3172 `arpa` / RFC 7686 `onion` trees), `is_at_or_under(host, domain)` using `IDNA_2008` and `Name.is_subdomain`, and `ConfiguredDomain` / `OptionalConfiguredDomain` Pydantic validators.
- [x] Added the `[idna]` extra to `dnspython[idna]==2.8.0` in `pyproject.toml`.
- [x] Rewired `core/validation.py`, `commands/k8s/networking.py`, `ai/spend/pricing.py`, `ai/common_tools.py`, `ai/harness/agents.py`, `ai/agents/capabilities.py`, `config/settings.py`, `sandbox/models.py`, and `security/reference_extractor.py`, and removed `CONST_LOCAL_DOMAIN_SUFFIXES`, `_is_fqdn_url`, `_canonical_host`, and `_in_domains`.
- [x] Added offline parametrised unit tests covering PSL classification, Ingress lookalike and malformed host filtering, `_should_update_url` private-zone preservation, SSRF pre-DNS rejection, IDNA 2008 domain matching, capability/settings domain validation, browser navigation egress, and sandbox policy generation.

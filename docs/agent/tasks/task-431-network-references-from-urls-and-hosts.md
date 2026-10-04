# Task: Network references come from URL and host arguments, not inspection of every string (#431)

**Issue**: [#431](https://github.com/dan-petty/devops-cli/issues/431)
**Status**: Done
**Milestone**: v0.2.26
**Priority**: priority/p1-high
**Scope**: type/fix, scope/security, priority/p1-high

## Description
Replaces heuristic bare-word and domain string inspection in `devops_cli.security.reference_extractor` with a strict, principled two-element definition:
1. A URL with a host in any scheme (`urllib.parse.urlsplit`).
2. An IP literal (`ipaddress`).

Bare words (e.g. `localhost`, `example.internal`, `api.datadoghq.com`, `ghcr.io`, `host: db.vendor-x.io`) are never extracted as network references. Dead heuristic constants, regexes, and domain-extraction visitors are completely eliminated without backward compatibility shims.

## Acceptance Criteria
- [x] Network references extracted across the repository consist exclusively of URLs and IP literals; bare words, hostnames, and arbitrary dotted identifiers are never classified as network references.
- [x] Deleted open-ended constants and shims: `CONST_BRANCH_PREFIXES`, `CONST_CODE_CONFIG_PREFIXES`, `CONST_COMMON_PROPERTY_SUFFIXES`, `CONST_TELEMETRY_CALL_NAMES`, `CONST_STANDARD_RECEIVER_IDENTIFIERS`, `CONST_EXCLUDED_FILE_MIME_TYPES`.
- [x] Deleted dead functions and classes in `devops_cli.security.reference_extractor`: `_get_workspace_filenames`, `_is_routable_dns_ip`, `_is_resolvable_domain`, `_is_metric_or_telemetry_context`, `_is_known_python_module`, `is_file_reference`, `is_code_or_config_reference`, `is_network_domain`, `_extract_domain_reference`, `PythonSymbolContext`, `PythonSymbolVisitor`, `_parse_python_file_symbols`, `_resolve_attribute_chain`, `_resolve_call_func`.
- [x] Python AST walk appends all string constants directly to literals without telemetry or identifier suppression heuristics, extracting URLs and IPs in dictionary keys and call arguments.
- [x] Registry URLs are skipped by host only via `is_trusted_registry_host(host: str) -> bool` matching `CONST_EXCLUDED_PUBLIC_REGISTRIES`.
- [x] Eliminated `"domain"` reference type across `src/devops_cli/models/vulnerability.py`, `src/devops_cli/output/formatters/tables.py`, and `src/devops_cli/security/reference_extractor.py`.
- [x] No DNS lookups or socket resolution performed during reference extraction.
- [x] Acceptance grep verifies 0 occurrences of deleted symbols and `"domain"` reference types.
- [x] Gated CI quality gates (`uv run devops ci`) pass 100%.

## Deliverables
- [x] `src/devops_cli/config/constants.py`: Removed `CONST_BRANCH_PREFIXES`, `CONST_CODE_CONFIG_PREFIXES`, `CONST_COMMON_PROPERTY_SUFFIXES`, `CONST_TELEMETRY_CALL_NAMES`, `CONST_STANDARD_RECEIVER_IDENTIFIERS`, `CONST_EXCLUDED_FILE_MIME_TYPES`.
- [x] `src/devops_cli/config/__init__.py`: Removed deleted constants from re-exports.
- [x] `src/devops_cli/models/vulnerability.py`: Changed default reference type to `"url"`.
- [x] `src/devops_cli/output/formatters/tables.py`: Changed table formatter reference fallback to `"url"`.
- [x] `src/devops_cli/security/__init__.py`: Removed `is_file_reference` and `is_network_domain` re-exports.
- [x] `src/devops_cli/security/reference_extractor.py`: Replaced heuristic bare-word/domain inspection with URL and IP parsing, implemented `is_trusted_registry_host`, removed dead helpers and symbol visitors.
- [x] `tests/test_reference_extractor.py`: Comprehensive test suite with structural tuple equality assertions covering DNS safety, bare word rejection, multi-scheme URLs, registry filtering, and Python literal extraction.
- [x] `tests/test_codebase_hygiene_and_shims.py`: Removed deleted symbol assertions.
- [x] `tests/test_review_pipeline.py` & `tests/test_review_report_summary.py`: Updated test fixtures and assertions from `"domain"` to `"url"`.
- [x] `changelog.d/431.md`: Added release changelog fragment.

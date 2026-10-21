# Task: Dependency Advisories and Package Inventory from osv-scanner (#1146)

**Issue**: [#1146](https://github.com/dan-petty/devops-cli/issues/1146)
**Scope**: scope/security
**Feasibility**: Verified that `osv-scanner` version 2.6.0 runs over target repository lockfiles with an offline database snapshot cached under `.data/cache/osv_db` (or custom cache directory) with a 24-hour TTL timestamp. The process edge fake (`scanner_fake` and `recorded_runs.json`) records `osv-scanner` v2.6.0 output deterministically so all tests run offline with zero external network access, zero live models, and zero real binaries executed in test suites.

## Description

- [x] Integrate `osv-scanner` 2.6.0 declarative adapter (`OsvScanner`) into security scanner registry targeting lockfiles offline.
- [x] Cache offline database snapshot digest with 24-hour TTL (`CONST_OSV_OFFLINE_DB_TTL_SECONDS = 86400.0`) and record snapshot digest as a review profile input.
- [x] Attach `AdvisoryAnchor` models carrying `purl@locked-version`, snapshot digest, advisory id, and database origin to dependency findings.
- [x] Preserve exact advisory severity from vulnerability record (`database_specific` or `ecosystem_specific`) without defaulting to HIGH; map unknown/unspecified values to UNKNOWN.
- [x] Generate CycloneDX 1.5 software bill of materials (SBOM) inventory components from scanned lockfiles and record in `EnvironmentFacts` and finding properties.
- [x] Detect missing lockfiles for recognized package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, etc.) and report coverage gaps.
- [x] Remove live OSV client queries and regex package extraction from the review pipeline.
- [x] Guard external network threat intelligence (Shodan InternetDB and Cloudflare Radar) behind an explicit opt-in flag (`threat_intel=False` by default).
- [x] Register `osv-scanner` v2.6.0 in test scanner fake harness and recorded test runs.
- [x] All unit and integration tests run offline with recorded fakes in <1s per test without network, real scanners, or live models.
- Pending a person: on the S11 subject, verify results agree with `uv audit`.

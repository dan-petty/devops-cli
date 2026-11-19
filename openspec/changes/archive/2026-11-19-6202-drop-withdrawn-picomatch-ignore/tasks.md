# Tasks

## 1. Ignore entry

- [x] 1.1 Remove the GHSA-fc5q-39xc-vjpf entry from `.npm-audit-ignore.yaml` and keep an empty `vulnerabilities` list
  - Verification: `$ uv run devops ci audit`
- [x] 1.2 Confirm that the ignore file and SECURITY.md do not name GHSA-fc5q-39xc-vjpf
  - Verification: `$ ! git grep -n fc5q -- .npm-audit-ignore.yaml SECURITY.md`

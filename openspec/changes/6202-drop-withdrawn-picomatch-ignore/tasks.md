# Tasks

## 1. Ignore entry

- [ ] 1.1 Remove the GHSA-fc5q-39xc-vjpf entry from `.npm-audit-ignore.yaml` and keep an empty `vulnerabilities` list
  - Verification: `$ uv run devops ci audit`
- [ ] 1.2 Confirm that no file outside the archive and the test fixtures names the advisory as ignored
  - Verification: `$ ! git grep -n fc5q -- .npm-audit-ignore.yaml SECURITY.md`

# Task #1145: Tested Semgrep Rule Pack for Review Recall Network-Exposure Entries

**Issue**: [#1145](https://github.com/dan-petty/devops-cli/issues/1145)
**Feasibility**: Confirmed against pinned Semgrep 1.179.0 (`tools.lock`): `semgrep --test --metrics off src/devops_cli/review/rules` executes offline in ~6s, passes 1/1 on `k8s-networkpolicy-ingress-any.yaml` and `k8s-networkpolicy-ingress-any.test.yaml`, and matches both recall set NetworkPolicy manifests (`k8s/monitoring/networkpolicy.yaml:20` and `k8s/otel/networkpolicy.yaml:32`) at `38517a89ebd1439e245c08ce0d9ad9cd17932b74` without matching egress `0.0.0.0/0` blocks.

## Deliverables

- [x] Added MIT-licensed Semgrep rule `src/devops_cli/review/rules/k8s-networkpolicy-ingress-any.yaml` with `CWE-284` metadata and companion test suite `src/devops_cli/review/rules/k8s-networkpolicy-ingress-any.test.yaml` covering `ruleid:` cases for both recall NetworkPolicy shapes and `ok:` cases for a restricted RFC 5737 CIDR and an egress-only policy.
- [x] Updated `tests/fixtures/review_recall/recall_set.json` so every recall entry names its expected `tool` and `rule` (`semgrep` / `k8s-networkpolicy-ingress-any` for Network Exposure, `ruff` / `BLE001` for Error Handling, and `none` / `none` for the `docs/VISION.md` Security Claims entry).
- [x] Added `src/devops_cli/review/rules_pack.py` and `devops review rules test` (`--check`, `--rules-dir`, `--format`, `--dry-run`) to run `semgrep --test --metrics off` and write/verify `src/devops_cli/review/rules/rules.lock` with `(rule_sha256, test_sha256, semgrep_version)` per rule.
- [x] Included `src/devops_cli/review/rules` in Semgrep review scans (`src/devops_cli/security/semgrep.py`) and normalized pack rule `check_id` values.
- [x] Added path-filtered `rule-pack` job (`Rule Pack Tests`) to `.github/workflows/ci.yml` triggered when `src/devops_cli/review/rules/**` changes, installing pinned Semgrep and running `semgrep --test` and `devops review rules test --check` outside the local pre-push gate.
- [x] Added unit and offline gate tests in `tests/test_review_rules_pack.py` (all completing under 1 s with fakes).
- Pending a person: Run a full path review of `38517a89ebd1439e245c08ce0d9ad9cd17932b74` against the live homelab LLM stack and confirm both network exposure entries are reported in the review session output.

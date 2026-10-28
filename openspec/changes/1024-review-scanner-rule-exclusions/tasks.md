# Tasks

## 1. A review's scans leave out the rules that gave no valid finding

- [x] Add failing tests: a review's kube-linter config excludes `dangling-service`; a review's Semgrep command excludes the two rule ids and keeps the logger rule; a scan outside a review excludes no rule; the replay over the labelled S3 to S5 candidates (a new trimmed fixture) and the S11 to S21 labels drops no valid finding
  - Verification: `uv run devops ci test tests/security/test_review_rule_exclusions.py`
- [x] Add `_REVIEW_EXCLUDED_CHECKS` and the review config to `security/kubelinter.py`, delete `CONST_REVIEW_SCAN_KUBELINTER_CONFIG`, and add `_REVIEW_EXCLUDED_RULES` with `exclude_rules` through `build_semgrep_cmd` for a review's materialized targets
  - Verification: `uv run devops ci test tests/security/test_review_rule_exclusions.py tests/test_review_untrusted_tree.py tests/test_security_semgrep.py`
- [x] Record the Semgrep run of the adapter contract suite again with the real Semgrep 1.179.0
  - Verification: `uv run devops ci test tests/test_scanner_contract.py`
- [x] Delete the dead `non-literal-import` suppression from `.devops/review.toml`, name the tables in `docs/SELF_IMPROVEMENT.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1024-review-scanner-rule-exclusions`
- Pending a person: score lenient precision on the review redesign's tuning inputs (the S11 input and the loop input) with `devops review score` (#1138), and record it on #1024.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

# Design

## Where the exclusions live

Each table lives beside the adapter that reads it, and is private to it: `_REVIEW_EXCLUDED_CHECKS` in `security/kubelinter.py`, `_REVIEW_EXCLUDED_RULES` in `security/semgrep.py`. Each entry is a rule id and its reason.

- kube-linter reads its checks from the config that a review hands it (#972), so the review config is made from the table: `checks: {exclude: [...]}`.
- Semgrep has no config key that excludes a rule, so the review's command names `--exclude-rule <id>` for each. Only a review's isolated scan materializes its targets (`MaterializedTargets`), so the branch of `_build_scan_command` for them passes the table, and every other scan passes none.

## Rejected alternatives

- **A `[[suppressions]]` entry in `.devops/review.toml` with the path `**`.** A suppression is a reviewed exception for a path, with an expiry, read from the reviewed commit (#871). The reason for each of these rules is how a review runs the tool, or what the rule cannot decide, and it holds for every path. A suppression would also still run the rule and carry its findings to admission.
- **One kube-linter run over all the reviewed manifests, to keep `dangling-service`.** #1045's re-scope measured that such a run still reports `dangling-service` for a Service that selects Helm-deployed pods (comment on #1024, 2026-10-09).
- **A copy of the registry rules with the three rules removed.** The licence of the registry rules allows internal use only, and the repository is public. Exclusion by rule id copies no rule text.
- **Excluding `logger-credential-disclosure` too.** Its finding at `commands/config.py:514` in S3 to S5 was valid, and one of its S11 to S21 findings is labelled valid-strict. #1024 keeps it until #1138's labels show no valid finding from it after #1022.
- **The same exclusions for `devops scan`.** #1024 is about the review's configuration. A person who runs `devops scan` names the rules they want, and a test holds that such a scan leaves out no rule.
- **A new `isolation_arguments` hook on `BaseSecurityScanner`.** The flags of the files that an isolated scan is handed are read as flag and path pairs for the tool run record (`_tool_files`), so other arguments cannot join them. Semgrep already builds a review's command in its own branch for materialized targets, which needs no change to the base class.

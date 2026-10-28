# Proposal

## Why

Issue #1024: three scanner rules gave only false findings in the labelled reviews of this repository, and they fill every review with them.

- kube-linter `dangling-service`: 4 of 4 candidates in each of the review sessions S3, S4 and S5 of release/v0.2.25, 20 in S10, and 17 of 17 labelled findings in S11 to S21. A review runs kube-linter on one manifest at a time, so kube-linter does not see the pods of a sibling file or of a Helm release that the Service selects.
- Semgrep `non-literal-import`: 7 candidates in each of S3, S4 and S5, and 4 labelled findings in S11 to S21, all false. The imported names came from literals, static maps or `__getattr__`.
- Semgrep `exec-detected`: 1 candidate in S5, false. The `exec` runs a documented snippet of the repository in a test.

Semgrep `logger-credential-disclosure` stays. Its finding at `commands/config.py:514` in S3 to S5 was valid, and one of its S11 to S21 findings is labelled valid-strict.

## What Changes

- A review's kube-linter scan gets the config `checks: {exclude: [dangling-service]}` in place of `checks: {}`. kube-linter runs every other default check.
- A review's Semgrep scan names `--exclude-rule python.lang.security.audit.non-literal-import.non-literal-import` and `--exclude-rule python.lang.security.audit.exec-detected.exec-detected`. The repository holds only the rule ids, never the text of a registry rule.
- Each exclusion is an entry of a table beside its adapter, with its reason: `_REVIEW_EXCLUDED_CHECKS` in `security/kubelinter.py`, and `_REVIEW_EXCLUDED_RULES` in `security/semgrep.py`. `build_semgrep_cmd` gets an `exclude_rules` parameter.
- A scan outside a review, such as `devops scan sast` and `devops k8s security-audit`, runs every rule of its config, as before.
- `CONST_REVIEW_SCAN_KUBELINTER_CONFIG` leaves `config/constants.py`: one module reads it, so its table lives beside that module (CONTRIBUTING.md, "Closed Lists and Standard Parsers").
- The `.devops/review.toml` suppression of `non-literal-import` on `telemetry/memory_profiler.py` is deleted, because no review runs that rule.
- `docs/SELF_IMPROVEMENT.md` names the two tables.
- The recorded Semgrep run of the adapter contract suite is recorded again with the new command.
- The command that a review starts each scanner with is observable, so the change carries a spec delta: ADDED requirements in `scanner-adapters`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `scanner-adapters`: a review's kube-linter and Semgrep scans leave out the rules that gave no valid finding on this repository, and a scan outside a review leaves out none.

## Impact

- `src/devops_cli/security/kubelinter.py`, `src/devops_cli/security/semgrep.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/config/constants.py`.
- `.devops/review.toml`, `docs/SELF_IMPROVEMENT.md`.
- `tests/security/test_review_rule_exclusions.py` (new), `tests/fixtures/review_replay/s3_s5_scanner_candidates.json` (new), `tests/test_review_untrusted_tree.py`, `tests/test_security_semgrep.py`, `tests/fixtures/scanner_runs/recorded_runs.json`, `tests/support/fakes/scanners.py`.

## Feasibility

- kube-linter 0.8.3, the pinned version, run on 2026-10-28 on `k8s/llm/profiles/services.yaml` and `k8s/cloudflared/deployment.yaml`: with `checks: {}` it ran 31 checks and reported 16 `dangling-service` and 1 `no-anti-affinity`. With `checks: {exclude: [dangling-service]}` it ran 30 checks and reported only the `no-anti-affinity`.
- Semgrep 1.179.0, the pinned version: `semgrep scan --help` documents `--exclude-rule=VAL`, "Skip any rule with the given id. Can add multiple times". The cached `p/default` ruleset (1,074 rules) holds the three Semgrep ids as written above. A review's isolated scan of a file with an `exec`, an import of a variable name and a logged password reported all three rules before the change, and only `logger-credential-disclosure` after it. The real Semgrep ran the contract suite's command with the two flags, exited 0 and reported no error.
- A review's kube-linter scan of `services.yaml` through `run_kubelinter_scan(..., isolated=True)` reported 0 findings after the change, and `deployment.yaml` still reported its anti-affinity finding.
- The replay data exists: the candidates of the sessions `.data/reviews/20261002-180320`, `-200610` and `-205520` and the evaluation `.data/review-evaluation-20261002-s5.md`. The fixture keeps their 54 scanner candidates and the two persona candidates that S5 labelled valid, each with the label and the section of the evaluation that gives it. The S11 to S21 labels are in `tests/fixtures/review_labels/labels.json` (#1138).
- #1045's re-scope (comment on #1024, 2026-10-09) found that one kube-linter run over the whole manifest set still reports `dangling-service` for a Service that selects Helm-deployed pods, so `dangling-service` stays out of a review.

## Existing Tool Considered

Both tools have their own rule-id exclusion, and the change uses it and builds none: kube-linter's `checks.exclude` config key, and Semgrep's `--exclude-rule` flag. The change deletes `CONST_REVIEW_SCAN_KUBELINTER_CONFIG` and the `.devops/review.toml` suppression that the Semgrep exclusion makes dead.

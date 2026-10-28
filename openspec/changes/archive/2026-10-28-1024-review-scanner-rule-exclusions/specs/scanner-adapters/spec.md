## ADDED Requirements

### Requirement: A review's kube-linter scan leaves out dangling-service
The config that a review hands kube-linter SHALL exclude the check `dangling-service` and SHALL name no other check, so kube-linter runs every other default check.

#### Scenario: A review scans a manifest
- **WHEN** a review's isolated kube-linter scan runs on a manifest
- **THEN** the `kube-linter.yaml` in its working directory reads `checks: {exclude: [dangling-service]}`

### Requirement: A review's Semgrep scan leaves out two rules by rule id
A review's Semgrep scan SHALL name `--exclude-rule` for `python.lang.security.audit.non-literal-import.non-literal-import` and for `python.lang.security.audit.exec-detected.exec-detected`, and for no other rule. It SHALL keep `python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure`.

#### Scenario: A review scans a Python file
- **WHEN** a review's isolated Semgrep scan runs on a Python file
- **THEN** its command excludes exactly the two rule ids, and does not name the logger rule

### Requirement: A scan outside a review leaves out no rule
A Semgrep scan that is not a review's SHALL name no `--exclude-rule`.

#### Scenario: devops scan runs Semgrep
- **WHEN** Semgrep scans a file outside a review
- **THEN** its command names no `--exclude-rule`

### Requirement: The excluded rules drop no finding that was labelled valid
Replayed over the labelled scanner candidates of the review sessions S3 to S5 and the labelled findings of S11 to S21, the rules that a review leaves out SHALL drop no finding that is labelled valid.

#### Scenario: The labelled findings are replayed
- **WHEN** the exclusions that a review's scans are handed are applied to the labelled findings of S3 to S5 and of S11 to S21
- **THEN** they drop 12 `dangling-service`, 21 `non-literal-import` and 1 `exec-detected` candidate of S3 to S5, and 17 `dangling-service` and 4 `non-literal-import` findings of S11 to S21, none of them valid, and every valid finding stays

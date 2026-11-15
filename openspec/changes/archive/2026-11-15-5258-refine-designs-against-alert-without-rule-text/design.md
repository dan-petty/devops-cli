# Design

## Decisions
- Read the code-scanning alert with one GET request when an item names an alert number in title or body.
- Extract the alert number using regular expression matching `code-scanning/(?:alerts/)?(\d+)` or `alert\s+#?(\d+)`.
- Store `rule_description` on `CodeScanningAlert` mapped from `rule.description`.
- Add the alert URL to `allowed_urls` so validation preserves the alert as a verified source for key question answers.
- Inject the alert rule description into `VerificationInput.body` so the judge model evaluates the proposal against the rule text.

## Rejected alternatives
- Only supply the rule identifier: rejected because the model hallucinates requirements for unfamiliar rule identifiers.
- Query Trivy database directly: rejected because the code-scanning API already supplies the exact rule description reported during CI.

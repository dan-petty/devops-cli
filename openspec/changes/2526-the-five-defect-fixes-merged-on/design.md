# Design

## Decisions

- **Place each guardrail in the single surface that best fits its defect class.**: Each surface has existing content that the guardrail extends, and the defect class matches the surface scope. Placing all five in one surface would dilute the relevance.
- **Write guardrails as sentences in the existing numbered items and sections, not as new sections.**: The items already hold rules of the same class. A new section would fragment the rule set and add no structure a reader needs.
- **Create a new capability `hardening-surface-guardrails` for the spec delta.**: No existing capability covers the declared hardening surfaces. The guardrails are project-level rules that constrain future code, which is observable behavior that a spec delta must record.

## Rejected alternatives

- **Write all five guardrails as Semgrep rules in src/devops_cli/review/rules/.**: The five defect classes are architectural and process lessons, not code patterns that a Semgrep rule can express. The rules directory holds code-pattern rules with passing tests.
- **Place all five guardrails in SECURITY.md.**: The Loki CVE pin (#2470) is a dependency-management process rule, not a security rule. CONTRIBUTING.md already holds process rules for contributors.
- **Set skip_specs to true because the change only edits documents.**: The guardrails are declared hardening surfaces that the audit workflow checks. Adding a guardrail changes what the audit reports, which is observable behavior. The change carries a spec delta.

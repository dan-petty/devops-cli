## ADDED Requirements

### Requirement: Refine includes code-scanning alert details in proposal context and evidence
When an item names a code-scanning alert, refine SHALL read the alert metadata with one GET request, include the alert rule description in the proposal prompt context, allow the alert URL as a verified source, and record the rule requirement in the key questions design evidence.

#### Scenario: Item names a code-scanning alert
- **WHEN** Refine processes an item that names a code-scanning alert
- **THEN** The request context contains the alert rule description and the refined section holds the alert rule description under key questions

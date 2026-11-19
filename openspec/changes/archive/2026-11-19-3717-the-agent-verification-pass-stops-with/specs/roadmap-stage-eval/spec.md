## ADDED Requirements

### Requirement: The verify report names the stop reason of a failed case
The eval verify report SHALL record the typed stop reason of each failed case in its JSON and SHALL name it in its text.

#### Scenario: A case stops with a typed reason
- **WHEN** A case run stops with the reason `text_reply`.
- **THEN** The JSON holds that reason for the case and the text report names it.

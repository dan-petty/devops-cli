# Spec Delta

## ADDED Requirements

### Requirement: A delivery of the App bot's own write counts as self
The router SHALL count a delivery that the roadmap consumer refuses as the App bot's own write in `devops_cli_service_webhook_deliveries_total` with the outcome `self`, apart from the other ignored deliveries, and SHALL still answer it with HTTP 200 and status `ignored_own_write`.

#### Scenario: The bot's write and a repeated delivery
- **WHEN** a signed `issues` delivery arrives twice with one delivery id, and another arrives whose sender is the App's bot
- **THEN** the counter has one `issues` delivery with the outcome `ignored` and one with the outcome `self`

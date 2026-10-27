# Spec Delta

## ADDED Requirements

### Requirement: The gateway routes embeddings with simple-shuffle across order 1 tiers
The gateway configuration SHALL configure a routing group for the `qwen3-embedding:0.6b` model with `routing_strategy: simple-shuffle`, spreading sequential and parallel batches across all order 1 serving tiers.

#### Scenario: Gateway router settings
- **WHEN** the gateway configuration is loaded
- **THEN** `router_settings.routing_groups` contains a group for `qwen3-embedding:0.6b` with `simple-shuffle` routing strategy

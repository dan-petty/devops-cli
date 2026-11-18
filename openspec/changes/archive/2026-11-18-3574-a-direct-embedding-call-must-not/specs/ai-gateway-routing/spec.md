## ADDED Requirements

### Requirement: Guard against a one-model tier
A test MUST fail and name the tier when the Service of `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL` selects a tier that loads one chat model.

#### Scenario: The embedding URL names the 48 GiB tier
- **WHEN** `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL` names the Service of a tier in `SINGLE_MODEL_TIERS`
- **THEN** the test fails and names that tier.

#### Scenario: The embedding URL names the embedding tier
- **WHEN** `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL` names the Service of a tier that loads an embedding model
- **THEN** the test passes.

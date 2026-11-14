## ADDED Requirements

### Requirement: The Valkey embedding key holds the request identity
The Valkey embedding cache SHALL key each vector by the provider and the model name that the embedding request sends, as the disk tier does, so a direct OpenAI request and a gateway request for one configured model use different keys.

#### Scenario: A direct OpenAI write and a gateway read
- **WHEN** a direct OpenAI engine writes the vector of a text and a gateway engine with the same configured model reads that text
- **THEN** the gateway engine gets no vector from Valkey and sends the text to the gateway

#### Scenario: A document and a query keep two keys
- **WHEN** one text is embedded as a document and as a query
- **THEN** Valkey holds two keys for the text

## MODIFIED Requirements

### Requirement: Embeddings are cached by the hash of the text
The job SHALL embed through `EmbeddingsEngine` with its memory, Valkey and disk tiers, and SHALL keep no embedding file of its own. The text of an item SHALL be its title and its body outside the sections of the refine job and the alternatives job, and each distinct text SHALL go to the embedder once in a run.

#### Scenario: An unchanged board embeds nothing
- **WHEN** the job runs twice over the same open items, each run with a new engine, and the configured Valkey refuses each connection
- **THEN** the second run sends no request to the embedding model, and `devops_cli_embedding_cache_lookups_total` counts a disk hit for each text of the second run

#### Scenario: An edit embeds one item
- **WHEN** a person edits the body of one item between two runs
- **THEN** the second run sends the text of that one item to the embedding model

#### Scenario: A section of a job is no edit
- **WHEN** the refine job writes its section into the body of an item
- **THEN** the text that the job embeds for that item does not change

#### Scenario: A different model
- **WHEN** the model name of the embedding task changes between two runs
- **THEN** the second run sends the text of every item to the embedding model again

#### Scenario: Items with the same text
- **WHEN** two open items have the same title and the same text of a person
- **THEN** the embedder gets that text once, and both items get its vector

#### Scenario: No file of its own
- **WHEN** a run ends
- **THEN** the folder of the job under the data directory holds the plan and no embedding file

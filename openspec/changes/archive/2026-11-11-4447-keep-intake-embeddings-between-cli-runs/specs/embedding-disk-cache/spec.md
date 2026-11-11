## Purpose

The disk tier of the embedding cache keeps the vectors of intake between two runs of the CLI, so a run sends only the texts that changed to the embedding model.

## ADDED Requirements

### Requirement: A second intake run reads its embeddings from disk
The embedder of intake SHALL keep each vector from the model in a SQLite file under the data directory. A later run with an empty memory cache SHALL send no embedding request for a text whose vector the file holds, also when Valkey refuses each connection.

#### Scenario: Two intake runs over settled items
- **WHEN** two intake plan runs over the same two items and one candidate each build their own embedder, and the configured Valkey refuses each connection
- **THEN** the first run sends one `/v1/embeddings` request and the second run sends none

### Requirement: The disk cache key holds the provider, the model and the text
The disk cache SHALL key each vector by the provider, the model name that the embedding request sends, and the SHA-256 of the text that the model gets. A changed text, another model or another provider SHALL be a miss. Only the texts that miss SHALL go to the model, and a hit SHALL give the floats that the model sent.

#### Scenario: Two of five texts changed
- **WHEN** a run embeds five texts and a second run embeds the same five texts with two of them changed
- **THEN** the second run sends only the two changed texts to the model

#### Scenario: Another model
- **WHEN** a run embeds a text, and a second run embeds the same text with another embedding model
- **THEN** the second run sends the text to the model

#### Scenario: A direct OpenAI request and the gateway
- **WHEN** a run with the provider `openai` and no gateway embeds a text for the model `qwen3-embedding:0.6b`, so that the request names `text-embedding-3-small`, and a second run embeds the same text through the gateway
- **THEN** the second run sends the text to the model

#### Scenario: A second run gets the same vectors
- **WHEN** a run embeds two texts and a second run embeds the same two texts
- **THEN** the second run sends no request and gets the vectors of the first run

### Requirement: The disk cache is a cache only
The disk cache SHALL record one vector length for each model key. A stored value that is not a vector of that length SHALL be a miss, and the vector that the model then gives SHALL replace it. A write of vectors of a new length SHALL remove the vectors of the old length. When the file cannot be opened, read or written, the disk cache SHALL log a warning that names the file, and each text SHALL go to the model with no error.

#### Scenario: A corrupt entry
- **WHEN** the stored value of a text is two bytes, and two runs embed the text
- **THEN** the first of the two runs sends the text to the model, and the second sends nothing

#### Scenario: A vector of another length
- **WHEN** the stored value of a text is a valid array of two doubles, the recorded length is four, and a run embeds the text
- **THEN** the run sends the text to the model and gets the vector of four doubles

#### Scenario: The model gives vectors of a new length
- **WHEN** a run embeds `old row` as four doubles, a second run embeds `new row` as six doubles for the same model key, and a third run embeds both
- **THEN** the third run sends only `old row` to the model

#### Scenario: A file that is not a database
- **WHEN** the cache file holds text that is not a SQLite database, and a run embeds one text
- **THEN** the run sends the text to the model, gets its vector, and logs a warning that names the file

### Requirement: The disk cache removes vectors that no run used for 30 days
A lookup that finds a vector SHALL set its time of last use. Each write SHALL remove the vectors that no lookup or write used for 30 days.

#### Scenario: A read keeps a vector
- **WHEN** a run embeds `kept` and `dropped`, a run 20 days later embeds `kept`, a run 20 days after that embeds `new`, and a last run embeds `kept` and `dropped`
- **THEN** the last run sends only `dropped` to the model

### Requirement: Valkey answers before the disk cache
The embeddings engine SHALL look up a text in the memory cache, then in Valkey, then in the disk cache. A vector from the disk cache SHALL go into the memory cache and into Valkey.

#### Scenario: A disk hit fills Valkey
- **WHEN** only the disk cache holds a text, and two runs with an empty memory cache and one shared Valkey embed it
- **THEN** the first run counts a disk hit, the second counts a Valkey hit, and no run sends the text to the model

### Requirement: The memory cache holds one intake comparison set
The default memory cache of the embeddings engine SHALL hold at least 1,800 vectors.

#### Scenario: A second embedding of 1,800 texts in one process
- **WHEN** one engine with the default cache size embeds 1,800 distinct texts two times
- **THEN** the second time sends no request

## ADDED Requirements

### Requirement: A batch is halved only for input, timeout, or short vector replies
When a direct Ollama batch fails, `_embed_batch_with_subdivision` SHALL halve the batch and try each half again only when a node returned HTTP 400, 413, or 422, timed out, or returned HTTP 200 with fewer vectors than texts.

#### Scenario: Combined batch refused with HTTP 400, 413, or 422
- **WHEN** a fake Ollama node answers HTTP 400, 413, or 422 when a batch holds multiple texts and answers 200 for single texts or smaller halves
- **THEN** the engine halves the batch and returns the vectors of all texts

#### Scenario: One bad text in a batch returns 400
- **WHEN** a fake Ollama node refuses one text with HTTP 400 and answers 200 for every other text
- **THEN** the engine halves the batch so valid halves receive their vectors and raises `EmbeddingsError` with status 400 when only the refused text remains

#### Scenario: Timeouts and malformed 200 replies keep halving
- **WHEN** a fake Ollama node times out on a batch or returns one vector for two texts on HTTP 200
- **THEN** the engine halves the batch and returns the vectors of the texts

### Requirement: Permanent, network, and mixed node errors raise without halving
The engine MUST raise `EmbeddingsError` on the first failed batch without halving when every failed node returned HTTP 401, 403, 404, or 5xx, raised a connect error, or raised an unknown `EmbeddingsError` with no status that is not a vector count mismatch.

#### Scenario: Permanent HTTP 404 raises on 1 request for 128 texts
- **WHEN** a fake Ollama node answers HTTP 404 to a batch of 128 texts
- **THEN** the node receives 1 request and the engine raises `EmbeddingsError`

#### Scenario: Auth, server, connect, and unknown errors raise on 1 attempt
- **WHEN** a fake Ollama node fails a multi-text batch with HTTP 401, HTTP 403, HTTP 503, a connect error, or an `EmbeddingsError` with no status and no vector count mismatch
- **THEN** the node receives 1 attempt and the engine raises `EmbeddingsError`

#### Scenario: Two nodes fail with 404 and connect error
- **WHEN** one fake Ollama node answers HTTP 404 and a second node raises a connect error on a 2-text batch
- **THEN** each node receives 1 request and the engine raises `EmbeddingsError`

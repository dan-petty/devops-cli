# embedding-batch-size Specification

## Purpose
The number of texts that the embeddings engine sends in one embedding batch: how a slow or timed-out batch makes the batch size smaller, and how fast batches make it larger again.

## Requirements

### Requirement: A slow or timed-out batch halves the batch size
When a batch to a direct Ollama node takes longer than the latency threshold (`DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS`) or times out, the engine SHALL halve the batch size, to one text at the minimum. When a batch at the gateway or at an OpenAI-compatible API times out, the engine SHALL halve the batch size in the same way.

#### Scenario: The size stays at one text
- **WHEN** the batch size is 1 text, and each batch of a call takes longer than the latency threshold
- **THEN** the next call sends batches of 1 text

### Requirement: A batch larger than the size in use does not halve it
The engine SHALL NOT halve the batch size for a slow or timed-out batch that holds more texts than the batch size in use. An earlier decrease applies to that batch, so the parallel batches of one size halve the size once.

#### Scenario: Parallel slow batches halve the size once
- **WHEN** the batch size is 4 texts, one call embeds 8 texts in two batches that two workers send in parallel, and each reply takes longer than the latency threshold
- **THEN** the next call sends batches of 2 texts

#### Scenario: Parallel batches that time out on an Ollama node halve the size once
- **WHEN** the batch size is 4 texts, one call embeds 8 texts in two batches that two workers send in parallel, and the first request of each batch times out
- **THEN** the engine sends each batch again as two batches of 2 texts, and the next call sends batches of 2 texts

#### Scenario: Parallel gateway batches that time out halve the size once
- **WHEN** the batch size at the gateway is 4 texts, one call embeds 8 texts in two parallel batches, and the first request of each batch times out
- **THEN** the second request of each batch gets its reply, and the next call sends batches of 2 texts

### Requirement: Only a batch within the margin below the threshold counts as fast
A batch to a direct Ollama node SHALL count as fast only when it takes at most `DEFAULT_RAG_EMBEDDING_INCREASE_LATENCY_RATIO` of the latency threshold. A batch that is slower than that, but not slower than the threshold, SHALL stop the run of fast batches.

#### Scenario: A batch slower than the margin stops the run of fast batches
- **WHEN** the cooldown has passed, and one worker sends three batches that take the margin share of the threshold, a time between the margin and the threshold, and the margin share again
- **THEN** the batch size does not change, and it grows only after the next fast batch makes two fast batches in a row

### Requirement: The batch size grows back only after a cooldown
A fast batch SHALL count only when `DEFAULT_RAG_EMBEDDING_INCREASE_COOLDOWN_SECONDS` have passed since the last change of the batch size. After two fast batches in a row that count, the engine SHALL add two texts to the batch size, to the configured batch size at the maximum, and the cooldown SHALL start again.

#### Scenario: Fast batches in the cooldown do not grow the size
- **WHEN** a slow batch halved the batch size from 6 texts to 3 texts, and the batches of the next call are fast but come in the cooldown
- **THEN** the call after them sends batches of 3 texts

#### Scenario: Two fast batches after the cooldown grow the size by two texts
- **WHEN** the batch size is 3 texts, the cooldown has passed, and a call sends two fast batches
- **THEN** the next call sends a batch of 5 texts, and a call in the new cooldown does not grow the size

#### Scenario: The size does not grow past the configured size
- **WHEN** the configured batch size is 6 texts, the batch size is 5 texts, the cooldown has passed, and a call sends two fast batches
- **THEN** a call of 12 texts sends two batches of 6 texts

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

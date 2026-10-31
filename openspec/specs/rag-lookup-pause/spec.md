# rag-lookup-pause Specification

## Purpose
The pause of the RAG lookups of a review, chat or analysis run: how transient failures in a row pause the lookups, and how a probe after the pause resumes them or pauses them again.

## Requirements

### Requirement: Three transient failures in a row pause RAG lookups
After `CONST_RAG_CIRCUIT_BREAKER_FAILURES` (3) transient failures in a row, the RAG lookups SHALL pause for `CONST_RAG_CIRCUIT_BREAKER_PAUSE_SECONDS` (60 s), and a warning SHALL give the pause, the number of failures and the error of the failure that started the pause. A lookup in the pause SHALL return no context and SHALL send no request. A transient error, such as a 429 reply, SHALL NOT stop RAG for the run.

#### Scenario: Lookups in the pause send no request
- **WHEN** three lookups time out, and two lookups come 15 s and 30 s later
- **THEN** the two lookups return no context and send no request

### Requirement: A probe after the pause resumes the lookups
The first lookup after the pause SHALL be a probe. A probe that succeeds SHALL resume the lookups. A probe that fails SHALL pause the lookups for 60 s more, with one more warning.

#### Scenario: A probe that succeeds
- **WHEN** the pause has passed and the embedding model answers
- **THEN** the probe and the next lookup return context

#### Scenario: A probe that fails
- **WHEN** three lookups time out, and 60 s later the probe times out too
- **THEN** a lookup 59 s after the failed probe sends no request, the probe 60 s after the failed probe and the next lookup return context, and the two warnings are `RAG lookups paused for 60s after 3 failures: Timeout embedding query 3.` and `RAG lookups paused for 60s after 3 failures: Timeout embedding probe 1.`

### Requirement: qdrant-retry-wait-uses-clock-seam
The Qdrant retry SHALL wait between attempts through the sleep parameter of tenacity, supplied by the clock seam, and SHALL NOT call time.sleep directly.

#### Scenario: retry records waits on the clock fixture
- **WHEN** a Qdrant operation fails and the retry runs on the clock fixture
- **THEN** the clock fixture records the wait durations and no real wall-clock time is spent

#### Scenario: retry backoff sequence is recorded in order
- **WHEN** three retry attempts occur with the default backoff of 0.5 times the attempt number
- **THEN** the clock fixture records waits of 0.5, 1.0, and 1.5 seconds in that order

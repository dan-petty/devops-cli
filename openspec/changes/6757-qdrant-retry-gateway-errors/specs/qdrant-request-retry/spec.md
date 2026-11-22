## Purpose
Which failed requests of the Qdrant client get a retry. A transport error and an answer of a rate limit or of a gateway get a retry with a backoff. Each other error answer ends the operation at once.

## ADDED Requirements

### Requirement: A gateway or rate-limit answer gets a retry
A Qdrant operation whose request gets an answer with the HTTP status 429, 502, 503 or 504 SHALL send the request again after the backoff of the retry, up to `DEFAULT_MAX_RETRIES` attempts. The operation SHALL return the result of the first attempt that succeeds.

#### Scenario: A proxy answers 502 one time
- **WHEN** the server in front of Qdrant answers the upsert of a batch with 502 and an HTML body, and the next upsert with success
- **THEN** `upsert_points` returns the count of the points
- **AND** the client waited 0.5 s one time, and the server got the upsert two times

#### Scenario: A rate limit or a gateway answer
- **WHEN** the server answers the upsert of a batch with 429, 503 or 504, and the next upsert with success
- **THEN** `upsert_points` returns the count of the points after one wait of 0.5 s

### Requirement: Each other error status ends the operation at once
A Qdrant operation whose request gets an answer with any other error status, such as 400, 401, 403, 404, 408 or 500, SHALL raise its error after one attempt, with no wait. The status alone SHALL decide: a word in the answer, such as "Timeout" in the reason phrase of a 408, SHALL NOT make the answer transient.

#### Scenario: Qdrant answers 400
- **WHEN** the server answers the upsert of a batch with 400
- **THEN** `upsert_points` raises `QdrantClientError` with the text `Unexpected Response: 400`
- **AND** the client did not wait, and the server got the upsert one time

#### Scenario: The reason phrase holds the word Timeout
- **WHEN** the server answers the upsert of a batch with 408 (Request Timeout)
- **THEN** `upsert_points` raises `QdrantClientError` after one attempt and no wait

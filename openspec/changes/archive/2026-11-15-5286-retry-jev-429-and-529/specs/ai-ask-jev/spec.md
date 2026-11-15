## ADDED Requirements

### Requirement: A rate limit and a capacity limit are retried
The Jev provider client SHALL retry a response with status 429 or 529 through `AsyncHTTPX2TenacityTransport`, with `wait_retry_after` over an exponential fallback and at most `CONST_AI_JEV_RETRY_ATTEMPTS` attempts. It SHALL log each retry with the status and the attempt. It SHALL NOT retry another status.

#### Scenario: A 429 and then a 200
- **WHEN** the first request answers 429 and the second answers 200
- **THEN** the client makes two attempts and returns the 200

#### Scenario: A 529 and then a 200
- **WHEN** the first request answers 529 and the second answers 200
- **THEN** the client makes two attempts and returns the 200

#### Scenario: A 400
- **WHEN** the request answers 400
- **THEN** the client makes one attempt and returns the 400

#### Scenario: Three 429 answers
- **WHEN** each of the three attempts answers 429
- **THEN** the client stops after three attempts and raises the error to the caller

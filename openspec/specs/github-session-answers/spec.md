# github-session-answers Specification

## Purpose
The answers that the GitHub session stores for its next conditional GET, and the bound on their size in bytes, so the memory of a long-running process that shares one session does not grow with the answers it read.

## Requirements

### Requirement: Session answers are bounded by bytes
The GitHub session SHALL keep its stored GET answers within `DEFAULT_GH_SESSION_ETAG_CACHE_BYTES` bytes and `DEFAULT_GH_SESSION_ETAG_CACHE_SIZE` answers. When a new answer passes a bound, the answers read longest ago SHALL be dropped.

#### Scenario: The stored answers pass the byte budget
- **WHEN** the session reads eight answers of 300 KiB, with the byte budget at 1 MiB
- **THEN** the stored answers hold at most 1 MiB in total, and the next GET of the first URL carries no `If-None-Match`
- **AND** the next GET of the last URL carries the ETag of its answer.

#### Scenario: The heap after many rounds
- **WHEN** the status lane's round runs 50 times and each round reads one answer of a new URL
- **THEN** the heap after round 50 holds at most the slack of the rest of the process more than the heap after round 10.

### Requirement: An oversized answer is not stored
The session MUST return an answer that is larger than the whole byte budget, and MUST NOT store it.

#### Scenario: One answer is larger than the budget
- **WHEN** a GET returns an answer of 512 KiB, with the byte budget at 256 KiB
- **THEN** the call returns the whole answer with no error, and the next GET of that URL carries no `If-None-Match`.

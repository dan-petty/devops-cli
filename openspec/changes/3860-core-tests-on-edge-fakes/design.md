# Design

## Context

See proposal.md for the motivation and the scope (#3860, item 1 of #1333). The process fake is #775. The clock seam is #1320.

## Decisions

### 1. The tests of the pin keep the double of `subprocess.run`
- **Decision**: the tests that check the GitHub token that a child gets, and the environment of a child, run `DefaultProcessRunner` over a double of the stdlib `subprocess.run`. They assign no private name.
- **Rejected**: run them on `process_fake`. The fake replaces the runner, and the runner is where the pin and the environment are built. A test on the fake would check nothing of the pin. ADR 0007 allows the double of a stdlib edge for the test of the real implementation of a seam.
- **Rejected**: make `ProcessFake` build the environment and pin the token as the real runner does. That copies the logic of the runner into the fake, and the fake and the runner can then differ without a test noticing.

### 2. The token the tests expect is the one the floor pins
- **Decision**: a test that needs a token takes the `pin_github_session` fixture and expects its value. A test that needs no token calls `reset_github_token()`.
- **Rejected**: keep `monkeypatch.setattr(process, "_github_token", "A")`. It is a private assignment, and the floor already pins a token.

### 3. The retry interval reads the clock seam
- **Decision**: `_session_github_token` reads `clock.monotonic()`. The test moves the time with `clock.shift(...)`.
- **Rejected**: patch `time.monotonic`. It moves the clock of every library and of the runner. The seam exists for this read.
- **Rejected**: keep the assignment of `_github_lookup_failure` with an expired time. It is a private assignment, and the spec of the retry is the behavior over time, not the stored tuple.

### 4. The failure reasons run on `process_fake`
- **Decision**: the test of the reason in the unauthenticated error answers `gh auth token` through `process_fake` and calls the public `github_token()`.
- **Rejected**: leave it on the `subprocess.run` double. `github_token()` reaches the runner through `run_subprocess`, so the fake answers it, and the test then needs no stdlib double.

# Design

## Context

See proposal.md for motivation and scope (#1326).
Tests covering `commands/review.py`, `commands/analyze.py`, and `commands/ai.py` frequently patch internal methods such as `_execute_review_workflow`, `_find_session_dir`, and `LLMClient` methods directly. `commands/review.py` contains 2,484 lines mixing CLI argument parsing with workflow execution, finding tallies, corpus scoring, and PR review comments.

## Goals / Non-Goals

**Goals:**
- Extract review workflow orchestration and verdict judgment into `src/devops_cli/ai/review/`.
- Extract AI context collection and agent file generation into `src/devops_cli/ai/`.
- Route LLM client instantiation through the model factory seam.
- Route GitHub PR operations in review commands through the GitHub session seam.
- Eliminate internal patches and private imports across the 11 test files.
- Replace module-level `CliRunner()` instances with the `cli` fixture.

**Non-Goals:**
- Alter model prompts, analysis rules, or review scoring formulas.
- Change CLI command signatures or options for `devops review`, `analyze`, or `ai`.

## Decisions

### 1. Extract Review Logic to `src/devops_cli/ai/review/`
- **Decision**: Move PR review posting, verdict judgment, finding tally, corpus scoring, and sample selection to `src/devops_cli/ai/review/` as public functions.
- **Alternative considered**: Keep review workflow logic in `commands/review.py`.
  - *Rejected*: Architectural standard requires command modules to be thin CLI adapters over domain packages.

### 2. Route Model Requests Through the Model Seam
- **Decision**: Replace inline `LLMClient(...)` instantiations in `commands/ai.py` and `commands/analyze.py` with the model factory seam.
- **Alternative considered**: Monkeypatch `LLMClient.chat` and `LLMClient.preload_models` in tests.
  - *Rejected*: Issue #1307 prohibits patching internal methods; external process and model edges must be doubled via shared fakes.

### 3. Route PR Review Comments Through `GitHubSession`
- **Decision**: Route review file retrieval and comment submission through the `GitHubSession` seam.
- **Alternative considered**: Keep direct `PyGithub` requests and patch `github.Github`.
  - *Rejected*: GitHub operations must route through the central GitHub edge seam to honor pacing, rate limiting, and test doubling.

## Risks / Trade-offs

- [Telemetry initialization side-effects in review tests] → Use `otlp: FakeCollector` and configure headless test environment to suppress interactive logfire login prompts.
- [Coverage threshold during logic extraction] → Verify package test coverage after moving functions from `commands/` to `ai/`.

# Proposal

## Why

Issue #1326 delivers Phase E package test refactoring for `devops review`, `devops analyze`, and `devops ai` subcommands under parent issue #1307. Tests currently patch `LLMClient` methods, internal review workflow orchestrators (`_execute_review_workflow`, `_find_session_dir`), settings loaders, and logfire initialization, while importing private symbols. This change migrates review and AI commands to edge fakes and model seams, extracts review and AI command logic into public functions in `ai/review/`, `ai/`, and `ai/analyze/`, and eliminates internal monkeypatching.

## What Changes

- Route AI model execution in CLI commands through the model seam (`FakeLLMClient` and model factories).
- Route GitHub API requests in `review` and `analyze` through the GitHub session seam rather than PyGithub.
- Move review command business logic (PR review posting, verdict judgment, finding tally, corpus scoring, sample selection) into `src/devops_cli/ai/review/` behind public functions.
- Move AI command context retrieval and prompt logic into `src/devops_cli/ai/` and `src/devops_cli/ai/rag/`.
- Replace internal patches and private imports across the 11 identified test files with shared edge fakes (`process_fake`, `keyring_store`, `github_api`, `cli`).
- Replace module-level `CliRunner()` instances with the `cli` fixture.
- This change alters no consumer-observed CLI behaviour or command syntax, so it sets `skip_specs: true`.
- This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/commands/review.py`: becomes a thin adapter delegating to `src/devops_cli/ai/review/`.
- `src/devops_cli/commands/ai.py`: delegates RAG retrieval, context collection, and agents generation to `src/devops_cli/ai/`.
- `src/devops_cli/commands/analyze.py`: delegates symbol-delta operations to `src/devops_cli/ai/analyze/`.
- `tests/commands/`: tests exercise CLI commands over edge fakes without monkeypatching product functions.

## Feasibility

- `FakeLLMClient` and the model seam provide deterministic model responses for chat, completion, and streaming.
- `GitHubApiFake` and `github_api` provide full REST/GraphQL interception for PR file listing and review comments.
- `KeyringFake` and `keyring_store` provide hermetic credential isolation.
- `FakeCollector` (`otlp`) captures telemetry metrics and spans without external endpoints.

## Existing Tool Considered

- `FakeLLMClient` simulates LLM model completions without network egress.
- `GitHubApiFake` isolates GitHub HTTP operations.
- `ProcessFake` isolates process execution.
- Reusing the existing shared fakes removes 136 internal patch sites and 20 private imports, maintaining harness consistency.

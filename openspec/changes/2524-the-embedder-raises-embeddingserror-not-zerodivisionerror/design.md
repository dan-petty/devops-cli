# Design

## Decisions

- **Place the guard in _embed_ollama after _get_ollama_urls returns, before any batch computation.**: The function that consumes the URL list validates it at entry. This is the standard guard-at-entry pattern and keeps the check next to the code that would crash.
- **Replace devops roadmap intake with gh issue create in the workflow.**: The workflow already has issues: write permission and GH_TOKEN. No model credential is needed. The finding is specific to a PR number, so duplicate risk is low.
- **Use ERRORS.rag.embedding_no_provider for the guard's error message.**: This is the same message the existing EmbeddingsError at the bottom of _dispatch_embed uses. It names the model and provider, which is what a caller needs to act on.

## Rejected alternatives

- **Guard in _dispatch_embed before calling _embed_ollama.**: _dispatch_embed already has the no-provider EmbeddingsError at its bottom. Adding a URL check there duplicates the check that _embed_ollama must own, and _embed_ollama is the function that uses the URL list.
- **Add a --no-embed flag to devops roadmap intake.**: It adds a new CLI surface for a one-off workflow need. The workflow already has the GitHub API access it needs via gh issue create.
- **Scope the handoff step to run only when a model credential is present.**: The finding is lost on every runner without a model. The issue body says the finding must be filed, not skipped.

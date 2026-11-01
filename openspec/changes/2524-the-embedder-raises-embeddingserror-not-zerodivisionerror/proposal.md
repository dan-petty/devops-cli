# Proposal

## Why

#2524: devops roadmap intake stops with ZeroDivisionError when ai.provider is ollama and ai.ollama_urls is empty. The hardening audit workflow hits this crash on every failed run and loses its findings. After the crash is fixed, the workflow still cannot file findings because the runner has no model credential.

## What Changes

- Add a guard in _embed_ollama that raises EmbeddingsError with the embedding_no_provider message when the Ollama URL list is empty.
- Replace the hardening audit intake handoff with gh issue create so it works on a runner with only GH_TOKEN and no model credential.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `embedding-batch-size`: Embedder raises EmbeddingsError for empty Ollama URL list
- `review-filed-findings`: Hardening audit files finding without a model credential

## Impact

- Code: `src/devops_cli/ai/rag/embeddings.py`, `.github/workflows/defect-pr-hardening-audit.yml`
- Tests: `tests/ai/rag/test_embeddings.py`, `tests/workflows/test_defect_pr_hardening_audit.py`

## Feasibility

- The embedder code at src/devops_cli/ai/rag/embeddings.py shows _embed_ollama calls _get_ollama_urls() and then uses len(urls) in a modulo at line 988. When urls is empty, this causes ZeroDivisionError. The _dispatch_embed method routes provider == ollama to _embed_ollama without checking the URL list, so the EmbeddingsError at the bottom of _dispatch_embed is never reached.
- The workflow at .github/workflows/defect-pr-hardening-audit.yml shows the handoff step runs uv run devops roadmap intake. The workflow declares issues: write permission and sets GH_TOKEN. The gh CLI is available on GitHub-hosted runners.
- First checks: uv run devops ci test tests/ai/rag/test_embeddings.py to verify the guard raises EmbeddingsError. uv run devops ci test tests/workflows/test_defect_pr_hardening_audit.py to verify the workflow step uses gh issue create.

## Existing Tool Considered

No external tool covers this need. The fix is a guard clause in the project's own embedder and a workflow step change. Written cost: about 5 lines of guard code in _embed_ollama, about 3 lines of workflow YAML, and about 15 lines of test. Total about 25 lines to build, keep and fix. No internal code is deleted.

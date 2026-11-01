### Problem Description

`devops roadmap intake` stops with `ZeroDivisionError: division by zero` when `ai.provider` is `ollama` and `ai.ollama_urls` is empty. `Embedder._dispatch_embed` (`src/devops_cli/ai/rag/embeddings.py`) sends the provider `ollama` to `_embed_ollama` without a check of the URL list. `_embed_ollama` then computes `batch_idx % len(urls)` (`_embed_single_batch`) with an empty list. The clean `EmbeddingsError` with the message `embedding_no_provider`, two lines lower in `_dispatch_embed`, is never reached.

The workflow `.github/workflows/defect-pr-hardening-audit.yml` hits this on every failed audit. Its step "Hand unhardened defect finding to intake" runs `uv run devops roadmap intake --confirm` on the GitHub runner, which has no Ollama URL. On 2026-10-28 the step failed five times with the same traceback, so the audit filed none of its five findings (runs 40726982400, 40739487773, 40747696823, 40758319104 and 40758364472, for PRs #2446, #2470, #2488, #2521 and #2522).

A second limit is in the same step: the runner has only `GH_TOKEN`, and no model or embedding credential. After the crash is fixed, intake stops with `EmbeddingsError` in place of `ZeroDivisionError`, so the handoff still cannot file the finding from the runner.

### Reproduction Steps

1. Use a config with `ai.provider: ollama` and no `ai.ollama_urls` (the state of the GitHub runner).
2. Run `uv run devops roadmap intake --title "fix(x): y" --body-file <file> --confirm`.
3. See the traceback that ends in `ZeroDivisionError` in `_embed_single_batch`.

### Expected vs Actual Behavior

Expected: with no Ollama URL, the embedder raises `EmbeddingsError` that names the missing setting, and the command reports it through the exit seam with no traceback. The hardening audit hands its finding to the roadmap by a path that works on a runner with no model, or the audit step is scoped so that it does not run where it cannot work.

Actual: an uncaught `ZeroDivisionError` with a traceback, and the audit finding is lost.

### Environment Diagnostics

GitHub-hosted runner `ubuntu-24.04`, `UV_PYTHON` 3.14, `main` at 2026-10-28.

### Logs, Traces, or Terminal Output

```
src/devops_cli/ai/rag/embeddings.py:825 in _dispatch_embed -> return self._embed_ollama(prefixed_miss)
src/devops_cli/ai/rag/embeddings.py:995 in _embed_ollama
src/devops_cli/ai/rag/embeddings.py:988 in _embed_single_batch -> start = batch_idx % len(urls)
ZeroDivisionError: division by zero
```


Source: https://github.com/dan-petty/devops-cli/actions/runs/40758319104

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=0f7bc266fd52ad4b6ad23bf65b710cd20c398b18 -->
## Proposed design

### Problem statement
The embedder crashes with ZeroDivisionError when ai.provider is ollama and no Ollama URL is set, because _embed_ollama computes a modulo over an empty URL list. The hardening audit workflow hits this crash on every failed run and loses its findings. After the crash is fixed, the workflow still cannot file findings because the GitHub runner has no model credential for the intake command's RAG step.

### Acceptance criteria

### Requirement: Embedder raises EmbeddingsError for empty URL list
When ai.provider is ollama and no Ollama URL is configured, the embedder SHALL raise EmbeddingsError with the embedding_no_provider message and no traceback.

#### Scenario: Empty URL list with ollama provider
- **WHEN** ai.provider is ollama and ai.ollama_urls is empty and embed_texts is called with one text
- **THEN** EmbeddingsError is raised with the embedding_no_provider message and no ZeroDivisionError traceback appears

### Requirement: Hardening audit files finding without a model
The hardening audit workflow SHALL file its finding as a GitHub issue using a path that requires no model or embedding credential.

#### Scenario: Workflow step runs on a runner with only GH_TOKEN
- **WHEN** the hardening report step fails and the runner has no model credential
- **THEN** a GitHub issue is created with the finding title and body and the workflow step exits with code 0

### Existing Tool Considered
No external tool covers this need. The fix is a guard clause in the project's own embedder and a workflow step change. Written cost: about 5 lines of guard code in _embed_ollama, about 3 lines of workflow YAML, and about 15 lines of test. Total about 25 lines to build, keep and fix.

### Key questions
- **Where does the empty-URL guard go?**: In _embed_ollama, after _get_ollama_urls returns, before any batch computation. The function that owns the URL list validates it at entry. (best practice) [sources: src/devops_cli/ai/rag/embeddings.py]
  - Rejected: Guard in _dispatch_embed before calling _embed_ollama. Rejected: _dispatch_embed already has the no-provider EmbeddingsError at its bottom. Adding a URL check there duplicates the check that _embed_ollama must own, and _embed_ollama is the function that uses the URL list.
  - Rejected: Guard in _embed_ollama after _get_ollama_urls. Chosen: the function that consumes the URL list validates it at entry. This is the standard guard-at-entry pattern and keeps the check next to the code that would crash.
- **How does the workflow file its finding without a model credential?**: Replace the devops roadmap intake call with gh issue create. The workflow already has issues: write permission and GH_TOKEN. No model is needed. (best practice) [sources: .github/workflows/defect-pr-hardening-audit.yml]
  - Rejected: Use gh issue create directly in the workflow. Chosen: the workflow already has issues: write and GH_TOKEN. The finding is specific to a PR number, so duplicate risk is low. Priority is set via labels. No model credential is needed.
  - Rejected: Add a --no-embed flag to devops roadmap intake. Rejected: it adds a new CLI surface for a one-off workflow need. The workflow already has the GitHub API access it needs.
  - Rejected: Scope the step to run only when a model credential is present. Rejected: the finding is lost on every runner without a model. The body says the finding must be filed, not skipped.
- **What error message does the guard raise?**: ERRORS.rag.embedding_no_provider formatted with model and provider, the same message the existing EmbeddingsError at the bottom of _dispatch_embed uses. [sources: src/devops_cli/ai/rag/embeddings.py]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "implement.branch": "fix/2524-the-embedder-raises-embeddingserror-not-zerodivisionerror", "implement.job": "devops-cli-runner-20261101-111632-012c", "implement.job_digest": "sha256:59fd1dd8fc8586f5c4fc86d4fe6818fa0a6706468788fcfc6508544092eb788e", "implement.job_state": "succeeded", "implement.spend": "{\"requests\": 49, \"input_tokens\": 1675103, \"output_tokens\": 10573}", "implement.stopped": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "724f34ddd794336a923d01a62b6681e38612748ba9abd2e2e7a35e4a4036bf30", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "386edf761c92715ef9524987cff9bd5b04885ba0fc070a52bdef9e69b7b5289d", "stage.branch": "fix/2524-the-embedder-raises-embeddingserror-not-zerodivisionerror", "stage.file_cap": null, "stage.groups": "[[\"Add EmbeddingsError guard for empty Ollama URL list\", 3582], [\"Replace intake handoff with gh issue create\", 3586]]", "stage.needs_split": null, "stage.pr": "2993", "stage.ready": "2993", "stage.sha": "df26506824df539a8b8f23d1dab8ed11aa1f5e31"} -->

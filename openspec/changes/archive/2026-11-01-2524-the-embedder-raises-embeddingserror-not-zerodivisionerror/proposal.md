# Proposal

## Why

#2524: `devops roadmap intake` stops with a `ZeroDivisionError` when `ai.provider` is `ollama` and no Ollama URL is set. The workflow `.github/workflows/defect-pr-hardening-audit.yml` runs that command on a runner that has only `GH_TOKEN`. The step fails on every failed audit and the audit loses its finding. After the crash is fixed, intake still cannot run on that runner, because it needs a model to embed and to propose. The workflow needs a way to file its finding that uses no model.

## What Changes

- The embedder raises an `EmbeddingsError` that names `ai.ollama_urls`, in place of the `ZeroDivisionError`, when the Ollama URL list is empty. A new message `ERRORS.rag.embedding_no_ollama_urls` holds the text.
- The workflow step files the finding with the project command `devops gh issues create`, with the label `source/agent` and no priority label. The issue has no `priority/*` label, so the next intake round of the Service places it. The step no longer runs `devops roadmap intake`.
- The contract test of the workflow follows: it pins the new handoff and fails if the step runs a command that needs a model.
- The embedder change is observable, so it carries a delta in `configured-service-urls`. The workflow change is a CI change that no consumer observes, so it carries no delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `configured-service-urls`: ADDED requirement "The embeddings engine stops on a missing Ollama URL". The base requirement "AI callers use only configured endpoints" already says that a caller with no endpoint stops with an error that names the setting. The new requirement applies it to the embedder.

## Impact

- Code: `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/lang/en/errors.py`
- Workflow: `.github/workflows/defect-pr-hardening-audit.yml`
- Tests: `tests/ai/rag/test_rag_embeddings.py`, `tests/invariants/test_workflow_contracts.py`
- Existing code that stays: `EmbeddingsError`, `ERRORS.rag.embedding_no_provider` (still used by `_dispatch_embed` and pinned by `test_no_provider_configured_raises_and_caches_nothing`), `EmbeddingsEngine._get_ollama_urls`, the `_MockValkey` class of `tests/ai/rag/test_rag_embeddings.py`, and the command `devops gh issues create`.

## Feasibility

All commands ran on the worktree at `origin/main` on 2026-11-01.

- The crash is real. `git grep -n "if not urls" origin/main -- src/devops_cli/ai/rag/embeddings.py` prints nothing, so no guard exists. A script that builds `EmbeddingsEngine(AIConfig(provider="ollama", ollama_urls=[]), valkey_client=None)` and calls `embed_texts(["hello"])` printed `urls: []` and then `ZeroDivisionError division by zero`.
- The mechanism is as the issue says. `_dispatch_embed` (line 862) sends the provider `ollama` to `_embed_ollama` (lines 867-868). `_embed_ollama` (line 1021) reads `urls = self._get_ollama_urls()` (line 1023). The nested `_embed_single_batch` computes `batch_idx % len(urls)` (line 1033). The issue cites line 988 for the modulo. That line is stale: the modulo is at line 1033 on `main`.
- Nothing newer fixed or removed it. `git log -3 origin/main -- src/devops_cli/ai/rag/embeddings.py` shows no commit about the guard, and no open plan under `openspec/changes/` names `embeddings.py` or `test_rag_embeddings.py`. An open-issue search for `ollama_urls ZeroDivisionError` finds only #2524.
- The crash reaches the intake command with a traceback. `GatewayIntakeModel(AIConfig(provider="ollama", ollama_urls=[])).embed(["x"])` printed `intake embed -> ZeroDivisionError`. `GatewayIntakeModel.embed` wraps only `DevOpsCLIError` and `OSError` in `ModelGatewayUnreachableError` (`_FAILED_CALL`, `src/devops_cli/roadmap/intake_model.py`). `EmbeddingsError` is a `DevOpsCLIError`, so after the guard the failure reaches the exit seam with no traceback.
- The text of `embedding_no_provider` is wrong for this case. `src/devops_cli/lang/en/errors.py` lines 294-298 say that the provider "is not ollama, openai, copilot or gateway" and end with "Set ai.tasks.embedding.provider". Here the provider is `ollama`, and the missing setting is `ai.ollama_urls`. The issue says the error "names the missing setting", and the base spec `configured-service-urls` says that the error names `ai.ollama_urls`. So the guard needs its own message.
- The second limit is real. In `src/devops_cli/roadmap/intake.py`, `apply_intake` runs after `plan_intake`, and `_placement_target` calls `store.create_issue` only then. The plan step calls `model.embed` and `model.propose` (`triage` task). So an intake run on a runner with no model writes nothing, and the finding is lost. `devops roadmap intake --help` also says that a candidate is "every open issue with no priority/* label".
- The workflow step is as the issue says. `.github/workflows/defect-pr-hardening-audit.yml` line 55 is the step "Hand unhardened defect finding to intake" and line 81 runs `uv run devops roadmap intake ... --confirm`. The workflow has `issues: write` and sets `GH_TOKEN`. `devops gh api repos/dan-petty/devops-cli/actions/runs/40758319104/jobs` shows "Run hardening report: failure" and then "Hand unhardened defect finding to intake: failure".
- The new path needs no model. `devops gh issues create --help` lists `--title`, `--body`, `--label` and `--repo`. `devops gh issues create --repo dan-petty/devops-cli --title "fix(hardening): x" --body b --label source/agent --dry-run` printed the plan `gh issue create --repo dan-petty/devops-cli --title 'fix(hardening): x' --body b --label source/agent` and made no request. The label exists: `devops gh api repos/dan-petty/devops-cli/labels/source%2Fagent --jq .name` printed `source/agent`. A scratch run of `resolve_devops_argv` on the planned step command returned no finding, so the test `test_every_devops_command_the_workflows_actions_and_hooks_run_resolves` stays green.
- The path matches the documents. `docs/ROADMAP_WORKFLOW.md` row 1 (Capture) names "a new issue on GitHub" as a way to capture a candidate, beside the intake command.

## Acceptance

- Criterion "Embedder raises EmbeddingsError for empty URL list": group 1. One wording differs from the criterion. The criterion asks for the `embedding_no_provider` message. That message names `ai.tasks.embedding.provider`, which is wrong when the provider is `ollama`. The issue text under "Expected" asks for an error that "names the missing setting", and `configured-service-urls` already says the error names `ai.ollama_urls`. So group 1 adds the message `embedding_no_ollama_urls` that names `ai.ollama_urls`. The exception class, the missing traceback and the guard place stay as the criterion says.
- Criterion "Hardening audit files finding without a model": group 2. The step files the issue with `devops gh issues create`, which needs only `GH_TOKEN`. The contract test checks it offline. Pending a person: after the merge, the first defect pull request that adds no guardrail shows the filed issue in the live run. No test under `tests/` can run a GitHub runner.

## Existing Tool Considered

Part 1 is a guard of about 6 lines and one message in the project's own embedder, so no outside tool applies. Part 2 builds no tool. It reuses the project command `devops gh issues create`, which wraps the open `gh` CLI (`gh issue create`) that GitHub-hosted runners include. The workflow change replaces one line and adds a comment; the contract test changes by about 20 lines. The change deletes the workflow call to `devops roadmap intake` and the contract assertion that pins it.

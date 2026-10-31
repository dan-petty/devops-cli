# Tasks

## 1. Extract Review Domain Logic to `ai/review/`
- [ ] 1.1 Move PR review posting, verdict judgment, finding tally, corpus scoring, and sample selection to `src/devops_cli/ai/review/`; verify with `uv run pytest tests/ai/review/`
- [ ] 1.2 Regenerate documentation with `uv run devops docs generate --sync-readme`

## 2. Extract AI Command Logic to `ai/` and `ai/analyze/`
- [ ] 2.1 Move context collection and agents generation from `commands/ai.py` to `src/devops_cli/ai/`; verify with `uv run pytest tests/ai/`
- [ ] 2.2 Move symbol-delta logic from `commands/analyze.py` to `src/devops_cli/ai/analyze/`; verify with `uv run pytest tests/ai/analyze/`

## 3. Route Commands Through Model and GitHub Seams
- [ ] 3.1 Route `commands/review.py` and `commands/analyze.py` through `GitHubSession` and model factory; verify with `uv run pytest tests/commands/test_review.py`
- [ ] 3.2 Remove inline `LLMClient` constructions across `commands/ai.py` and `commands/analyze.py`; verify with `uv run pytest tests/commands/test_ai_cmd.py`

## 4. Test Files Migration to Edge Fakes
- [ ] 4.1 Migrate `test_ai_cmd.py`, `test_ai_prewarm.py`, `test_ai_ast_cli.py`, and `test_ai_spend_cli.py` to `process_fake`, `fake_llm`, and `cli` fixture; verify with `uv run pytest tests/commands/test_ai_cmd.py tests/ai/mcp/test_ai_prewarm.py tests/ai/ast/test_ai_ast_cli.py tests/ai/spend/test_ai_spend_cli.py`
- [ ] 4.2 Migrate `test_gateway_review_stall.py`, `test_llm_pool_metrics.py`, and `test_library_vector_tier.py` to edge fakes; verify with `uv run pytest tests/http/test_gateway_review_stall.py tests/ai/test_llm_pool_metrics.py tests/commands/test_library_vector_tier.py`
- [ ] 4.3 Migrate `test_review.py`, `test_review_pr_post.py`, `test_review_stage_flags.py`, and `test_review_repos.py` to edge fakes and `make_finding` builder; verify with `uv run pytest tests/commands/test_review.py tests/commands/test_review_pr_post.py tests/commands/test_review_stage_flags.py tests/ai/review/test_review_repos.py`

## 5. Verification and Quality Gate
- [ ] 5.1 Verify zero internal patches and zero private imports across migrated test files
- [ ] 5.2 Verify test names conform to ASD-STE100 and do not end in `_success`, `_failure`, `_basic`, or `_command`
- [ ] 5.3 Run `uv run devops openspec check` and `uv run devops ci`

## Workflow follow-up
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).

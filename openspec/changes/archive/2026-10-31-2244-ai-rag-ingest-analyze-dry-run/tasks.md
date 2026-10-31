# Tasks

## 1. Test Harness and Planned Request Builders

- [x] 1.1 Add failing unit tests verifying dry-run preview and zero external calls for the 21 commands in `tests/commands/test_ai_rag_ingest_analyze_dry_run.py` (`uv run pytest tests/commands/test_ai_rag_ingest_analyze_dry_run.py`)
- [x] 1.2 Implement planned request builders in `src/devops_cli/ai/ai_plans.py` for analyze, ingest, rag, and research commands (`uv run pytest tests/commands/test_ai_rag_ingest_analyze_dry_run.py`)

## 2. Analyze and Ingest Commands Dry-Run Classification

- [x] 2.1 Decorate `ai analyze` with `no-external-request` and implement request-plan dry-run for `ai analyze branch`, `ai analyze path`, and `ai analyze pr` in `src/devops_cli/commands/analyze.py` (`uv run pytest tests/commands/test_ai_rag_ingest_analyze_dry_run.py -k analyze`)
- [x] 2.2 Decorate `ai ingest library` with `no-external-request` and implement request-plan dry-run for `ai ingest docs`, `ai ingest index-libraries`, and `ai ingest query-library` in `src/devops_cli/commands/ai_ingest.py` (`uv run pytest tests/commands/test_ai_rag_ingest_analyze_dry_run.py -k ingest`)

## 3. RAG and Research Commands Dry-Run Classification

- [x] 3.1 Decorate `ai rag` with `no-external-request` and implement request-plan dry-run for `ai rag clear`, `ai rag drift`, `ai rag index`, `ai rag index-kb`, `ai rag query`, `ai rag search`, and `ai rag status` in `src/devops_cli/commands/rag.py` (`uv run pytest tests/commands/test_ai_rag_ingest_analyze_dry_run.py -k rag`)
- [x] 3.2 Decorate `ai research annotate` and `ai research forage` with `no-external-request` and implement request-plan dry-run for `ai research analogies`, `ai research model`, and `ai research socratic` in `src/devops_cli/commands/ai_research.py` (`uv run pytest tests/commands/test_ai_rag_ingest_analyze_dry_run.py -k research`)

## 4. Verification and Documentation

- [x] 4.1 Remove all 21 commands from `tests/fixtures/dry_run_gaps.json` and verify the ratchet passes (`uv run pytest tests/test_fastmcp_contracts.py`)
- [x] 4.2 Sync documentation using `uv run devops docs generate --sync-readme` (`git diff docs/ README.md`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).

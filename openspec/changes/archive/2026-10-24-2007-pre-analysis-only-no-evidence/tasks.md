# Tasks

## 1. The static scan flag gates the review evidence

- [x] 1.1 Write a failing test: a review with `--pre-analysis-only`, `--no-static-scan` or `--reporting-only` starts no analyzer, no Ruff, no mypy and no tool canary, in tests/test_scanner_tool_executor.py (`uv run devops ci test tests/test_scanner_tool_executor.py`)
- [x] 1.2 Call `_run_review_evidence` only in the static scan branch of `init_per_file_payloads` in src/devops_cli/ai/review/pipeline.py (`uv run devops ci test tests/test_scanner_tool_executor.py tests/test_review_stage_flags.py tests/commands/test_review_pre_analysis_only.py`)
- [x] 1.3 Say in the `--no-static-scan` help and in the knowledge base stage list that the static scan holds the Ruff, mypy and complexity evidence, and regenerate the documentation (`uv run devops docs generate --sync-readme`, then `uv run devops docs check`)

## 2. Verification

- [x] 2.1 Run the quality gate (`uv run devops ci`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

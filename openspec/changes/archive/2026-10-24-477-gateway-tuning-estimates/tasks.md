# Tasks

## 1. Gateway tuning cost from spend ledger

- [x] 1.1 Write failing tests for spend ledger cost extraction and probe fallback in tests/test_ai_gateway_tune.py (`uv run devops ci test tests/test_ai_gateway_tune.py`)
- [x] 1.2 Implement spend ledger cost integration in src/devops_cli/ai/gateway_tune.py (`uv run devops ci test tests/test_ai_gateway_tune.py`)
- [x] 1.3 Regenerate CLI documentation with `uv run devops docs generate --sync-readme`

## 2. No-load capacity estimation

- [x] 2.1 Write failing tests for GPU memory bandwidth scaling and --estimate flag in tests/test_ai_gateway_tune.py (`uv run devops ci test tests/test_ai_gateway_tune.py`)
- [x] 2.2 Implement bandwidth estimation and CLI flag in src/devops_cli/ai/gateway_tune.py and src/devops_cli/commands/ai_gateway.py (`uv run devops ci test tests/test_ai_gateway_tune.py`)
- [x] 2.3 Regenerate CLI documentation with `uv run devops docs generate --sync-readme`

## 3. Verification and OpenSpec archive

- [x] 3.1 Validate OpenSpec change structure and run gates (`uv run devops openspec check`)
- [x] 3.2 Run complete CI test suite and quality gates (`uv run devops ci`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

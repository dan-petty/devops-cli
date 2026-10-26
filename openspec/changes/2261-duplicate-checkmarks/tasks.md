# Tasks

## 1. Eliminate Duplicate Console Prefixes

- [x] 1.1 Add failing AST invariant test in `tests/test_output.py` that validates calls to leveled print functions and fails when messages begin with level prefix symbols (`uv run devops ci test tests/test_output.py`).
- [ ] 1.2 Remove redundant prefix symbols from message arguments across `src/devops_cli/commands/` and update `src/devops_cli/ai/knowledge_base/devops_cli/libraries/rich.md` (`uv run devops ci test tests/test_output.py`).
- [ ] 1.3 Introspect and synchronize documentation (`uv run devops docs generate --sync-readme`).

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

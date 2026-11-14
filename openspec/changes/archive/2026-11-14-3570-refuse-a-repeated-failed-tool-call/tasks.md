# Tasks

## 1. Refuse an unchanged repeat of a failed call

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/roadmap/implement/implement_trace.py`. Changes: `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_tool_log.py`.

- [x] 1.1 Keep the digest and the masked reason of each retry and failure, and refuse a call whose digest is in the map before its handler runs
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_tool_log.py` passes
- [x] 1.2 Add the cases: the earlier reason with a hidden path, a changed call, a repeated successful call, and the recorded digest
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_tool_log.py` passes

## 2. Run the gates

Kind: other. Reads: `tests/roadmap/implement/`. Changes: none.

- [x] 2.1 Run the gate of the branch
  - Verification: `$ uv run devops ci test tests/roadmap/implement` passes
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck` passes

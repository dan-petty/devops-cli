# Tasks

## 1. Fix the three review findings
kind: documents

- [x] 1.1 Keep the filing rule in `docs/SDLC.md` only, and link to it from `docs/ROUTINE_TASKS.md`, principle 6.
  - Verification: `$ test "$(git grep -l 'File one candidate at a time' -- '*.md')" = docs/SDLC.md`
- [x] 1.2 Write the Nested Time Limits text of `ARCHITECTURE.md` as an instruction that names #4678 and the stream-and-keepalive design of the tunnel.
  - Verification: `$ git grep -n '#4678' ARCHITECTURE.md`
- [x] 1.3 Make the board audit of `docs/ROUTINE_TASKS.md` on demand only, and remove the board step from the Cadence A final stage.
  - Verification: `$ ! git grep -n 'On Demand / Pre-PR\|Validate remote project views' docs/ROUTINE_TASKS.md`
- [x] 1.4 Run the document tests.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py tests/invariants/test_roadmap_workflow_doc.py tests/core/test_docs_routine_tasks.py`

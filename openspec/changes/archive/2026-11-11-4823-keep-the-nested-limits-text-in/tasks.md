# Tasks

## 1. Keep the two texts in the STE limits
kind: documents

- [x] 1.1 Split the Nested Time Limits bullet of `ARCHITECTURE.md` into a short lead and one sub-bullet for each instruction.
  - Verification: `$ git grep -n '^  - Set the step shorter than' ARCHITECTURE.md`
- [x] 1.2 Remove the copy of the board rule from `docs/ROUTINE_TASKS.md`, and keep the link to `docs/SDLC.md`.
  - Verification: `$ ! git grep -n 'No roadmap job reads the board' docs/ROUTINE_TASKS.md`
- [x] 1.3 Run the document tests.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py tests/invariants/test_roadmap_workflow_doc.py tests/core/test_docs_routine_tasks.py`

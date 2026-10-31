# Tasks

## 1. The document and its check
- [x] 1.1 Write `tests/invariants/test_roadmap_workflow_doc.py` and see it fail: the document does not exist; verify with `uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py`
- [x] 1.2 Write `docs/ROADMAP_WORKFLOW.md` with the purpose, the steps, the transitions, the labels and record keys, the stop and retry path, the gates, the manual path, the diagram and the planned changes; verify with `uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py`
- [x] 1.3 Add the document to the hand-written class of `CONST_DOCS_INVENTORY`; verify with `uv run devops docs check`
- [x] 1.4 Regenerate the documentation with `uv run devops docs generate --sync-readme`

## 2. The routes to the document
- [x] 2.1 Route the SDLC row of the table in `AGENTS.md` to the document, and merge the command row into the CONTRIBUTING row and the ADR row into the term row, so that the file stays within its cap (6,471 of 6,500 characters); verify with `uv run devops ci test tests/invariants/test_agents_md_claims.py`
- [x] 2.2 Shorten Phase 1 of `docs/SDLC.md` and link it to the document
- [x] 2.3 Add the document to `docs/index.md`
- [x] 2.4 Regenerate the documentation with `uv run devops docs generate --sync-readme`

## 3. Verification and archive
- [x] 3.1 Run `uv run devops ci fail-to-pass --base origin/main` and `uv run devops ci`
- [x] 3.2 Archive the change with `uv run devops openspec archive 2909-roadmap-workflow-document` and run `uv run devops openspec check`

## Workflow follow-up
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).

# Tasks

## 1. Design record

Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/roadmap/adr.py`, `.gitattributes`. Changes: `docs/adr/0025-generated-documents-stay-in-git-and-the-project-brain-cites-them.md` (new), `docs/adr/0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md`, `docs/adr/0012-releases-are-derived-by-release-please-from-trunk-and-milestones-are-planning-buckets.md`.

- [x] 1.1 Write ADR 0025, and add the amendment note to ADR 0023 and ADR 0012
  - Verification: `$ uv run devops docs check`
- [x] 1.2 Confirm that no living document says that the generated documents are built at publish. The ADRs and the OpenSpec changes are records of the docs inventory, so the search leaves them out.
  - Verification: `$ ! git grep -n -iE "(reference|generated) (pages|documents|docs) at publish" -- ':!docs/adr' ':!openspec/changes'`

## 2. Glossary

Changes: `CONTEXT.md`.

- [x] 2.1 Define "Generated document" and "Citation", and change "Project brain"
  - Verification: `$ uv run devops docs check`

## Workflow follow-up

- The items of tracker #4880 build the decisions: #4888 marks the generated documents, #4889 names the source of each generated page, #4920 adds the drift lane and #4921 adds the commit and the document class to the RAG points. Each adds its spec delta under `openspec/specs/project-brain/<area>/spec.md`.
- Pending a person: review the design record.

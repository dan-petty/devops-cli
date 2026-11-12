# Proposal: Keep the generated documents in git as cited sources of the project brain

## Why

Closes #4884. The rigid-rules decision Q12 of 2026-10-22 said to stop committing the generated reference documents, and ADR 0012 decision 12 still names an item that builds the reference pages at publish. On 2026-11-11 the owner reversed Q12: the reference documents stay, the design accommodates the project brain, and all content stays current. ADR 0023 does not name a document as a source of the brain. It has no citation form for a document and no cap for issues about document drift. Without a record, the next agent can follow Q12 again.

## What Changes

- New ADR 0025. It records these decisions:
  - the 52 generated files and the command matrix of `README.md` stay committed, marked `linguist-generated`, regenerated in the pull request that changes their source and checked by the `docs` row;
  - the brain reads documents from `main` through the RAG docs collection, by their class in the docs inventory, and each entry holds the citation `{path, commit, lines, span_hash, doc_class, generated_from?, adr_status?, as_of}`;
  - document drift has its own lane, at most 3 batch issues a week, apart from the 2 insight proposals of ADR 0023;
  - the precision rule: a check runs at pull request time only when its run on `main` shows 0 false positives;
  - ADR 0014 stays, and the pre-push hook runs no generator.
- ADR 0023 and ADR 0012 each get a note at their top that names ADR 0025.
- `CONTEXT.md` defines "Generated document" and "Citation", and changes "Project brain".
- No spec delta (`skip_specs: true`): the change adds documents only and changes no behavior that a consumer sees. The items of tracker #4880 that build the citation (#4921) and the drift lane (#4920) add their deltas under `openspec/specs/project-brain/<area>/spec.md`.

## Capabilities

None.

## Impact

- No behavior change. This pull request applies nothing to the cluster, the ConfigMap or a Secret.
- The alternatives check reads the ADRs in force under a cap of 8,192 tokens. The ADRs in force use 8,048 tokens on `origin/main` and 8,183 tokens with this change, so the check leaves no ADR out.
- The change fits one pull request.

## Feasibility

- The generated files were counted from `CONST_DOCS_INVENTORY` (class `generated`) in `src/devops_cli/config/constants.py` and `ls docs/commands`: 7 reference pages, 42 command pages and 3 stubs, 52 files and 1,088,290 bytes (`wc -c`) at e6f7cb97.
- `.gitattributes` was read: it marks `docs/CLI_REFERENCE.md` and `docs/commands/*.md` only.
- The `docs` row was read in `src/devops_cli/commands/ci.py`: it runs `devops docs check` and fixes with `devops docs generate --sync-readme`.
- The RAG docs collection `devops_docs` was read in `src/devops_cli/config/defaults.py` and `src/devops_cli/ai/rag/indexer.py`.
- ADR 0012 decision 12, ADR 0013, ADR 0014 and ADR 0023 were read on `origin/main`. ADR 0013 supersedes ADR 0012, and #4656 already replaced its Pages item.
- `git log --first-parent origin/main --since=2026-11-04` gives 624 commits, and 502 of them change `openspec/changes/`.
- The ADR budget was measured with `adr_of`, `_superseded` and `fit_to_budget` of `src/devops_cli/roadmap/adr.py` over `docs/adr/`, before and after the change.

## Existing Tool Considered

The MADR form that the ADRs of `docs/adr/` use, and the glossary form of `CONTEXT.md`. No build: the item is a record. The record keeps the open tools that the project already uses: the GitHub `linguist-generated` attribute, the `docs` row of `devops ci`, the RAG docs collection in Qdrant and the docs inventory. It rejects cogapp, because cog runs Python from the documents. The change deletes no internal code.

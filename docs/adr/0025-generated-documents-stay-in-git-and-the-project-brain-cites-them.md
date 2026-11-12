---
status: accepted
date: 2026-11-11
decision-makers: [owner]
issue: 4884
amends: ["0012", "0023"]
body-hash: 3b9e0fdb9df4c5161b4bf2214aaee6b3bb297212b11081379c2d6f09d7205636
---

# Generated documents stay in git, and the project brain cites them

The rigid-rules decision Q12 of 2026-10-22 said to stop committing the generated reference documents. On 2026-11-11 the owner reversed it: "keep reference docs, but update design to accomodate project brain and keeps all content up to date". ADR 0023 does not name a document as a source of the brain. It gives no citation form for a document and no cap for issues about document drift. This record sets them, so that no agent follows Q12 again. Tracker #4880 holds the items that build it.

## Context

Facts measured on `main` at e6f7cb97 on 2026-11-12:

- **52 generated files are in git.** The docs inventory (`CONST_DOCS_INVENTORY`, class `generated`) lists them: 7 reference pages (`docs/CLI_REFERENCE.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/ERRORS.md`, `docs/KNOWLEDGE_BASE.md`, `docs/MCP_TOOLS.md` and `docs/TELEMETRY.md`), 42 pages of `docs/commands/` and 3 instruction stubs (`CLAUDE.md`, `GEMINI.md` and `.github/copilot-instructions.md`). They hold 1,088,290 bytes. The command matrix of `README.md` is a generated block in a hand-written file.
- **A check keeps them current.** The `docs` row of `devops ci` runs `devops docs check`. `Static Analysis` fails when a generated document is not the output of its generator (ADR 0014).
- **Only 2 of 11 globs have the mark.** `.gitattributes` marks `docs/CLI_REFERENCE.md` and `docs/commands/*.md` as `linguist-generated`. The other 6 reference pages and the 3 stubs have no mark.
- **The RAG docs collection already holds the documents.** Each point holds the path, the first and the last line and a hash of the content, but no commit and no class of the docs inventory.
- **No run finds the drift that no check finds.** The standards inventory of 2026-11-11 found 5 stale and 9 partial statements, 22 moved test paths and rules that two documents both state.
- **Most pushes change an OpenSpec change.** 502 of 624 first-parent commits of `main` since 2026-11-04 change `openspec/changes/`.

## Decision

### 1. Generated documents stay in git

The 52 generated files and the command matrix of `README.md` stay committed. GitHub shows them, and the brain and the agents read them from `main`. For each generated document:

- `.gitattributes` marks it `linguist-generated` (#4888).
- The pull request that changes its source also regenerates it, with `devops docs generate --sync-readme` or `devops ai agents`.
- The `docs` row of `Static Analysis` refuses it when it is not the output of its generator.
- Nobody edits it by hand.

No item builds the reference pages at publish. The Pages workflow of #4656 builds the site from the committed `docs/`.

### 2. Documents are sources of the brain

The brain reads documents from `main` through the RAG docs collection, by their class in the docs inventory:

| Class | The brain reads | Extra citation field |
| :--- | :--- | :--- |
| `generated` | Each file | `generated_from` |
| `hand-written` | Each file: the standards documents, the other pages of `docs/`, `k8s/README.md`, the knowledge base and the skills. Of the three skill copies, `.agents/skills/` only. | None |
| `record` | The ADRs of `docs/adr/` only | `adr_status` |
| `tool-owned`, `tool-generated`, `prompt` | None by default | None |

- OpenSpec changes, `docs/agent/archive/` and the test fixtures stay out of a brain search by default.
- Agents find answers in these documents through the brain tools (#4671), and each answer gives its citation.
- An entry from a document is class C of ADR 0023 section 3. The document is its durable copy, and a rebuild reads the document again.
- One fact has one source: a document or the code. A brain entry cites its source and never holds the only copy of a fact.
- Each entry from a document holds one citation, `{path, commit, lines, span_hash, doc_class, generated_from?, adr_status?, as_of}`:
  - `path` is the path in the repository.
  - `commit` is a first-parent commit of `main`. A squash merge removes the commits of a branch, but each first-parent commit stays.
  - `lines` is the first and the last line of the span.
  - `span_hash` is a hash of the text of the span. A reader compares it with the text at the head commit to find a stale citation. #4479 moves a stale citation whose text matches one line.
  - `doc_class` is the class in the docs inventory.
  - `generated_from` is the source that a generated page names (#4889).
  - `adr_status` is the status of an ADR as `devops_cli.roadmap.adr` reads it: in force, amended or superseded.
  - `as_of` is the date of the commit.
- #4921 adds the commit and the document class to the points of the RAG docs collection.

### 3. Document drift has its own lane

- `devops docs drift` (#4920) finds the drift that no pull request check finds: moved paths, removed commands, flags and settings, closed issues named as open, dead links and stale numbers.
- Each finding names its `path:line` and its evidence. It files at most 3 batch issues a week, one for each area, with at most 20 findings in each. A setting holds the caps. These issues are apart from the 2 insight proposals a week of ADR 0023.
- Its first 2 runs only plan and file nothing, as the first weekly brain runs do.
- An ADR is a record, and nobody edits its text to remove drift. A finding in an ADR in force asks for a new ADR or a note at its top. A superseded ADR gets counts only.

### 4. The precision rule

A check runs at pull request time only when its run on `main` shows 0 false positives on the day that it lands. Each other check runs on the schedule, in the drift lane of section 3. A rule moves from the drift lane to the `docs` row after a clean run on `main`.

### 5. The pre-push hook runs no generator

ADR 0014 stays. The generator runs in the pull request that changes its source, and the `docs` row of CI checks the result. A pre-push hook with the file filter of the generated documents would run on about 80 percent of pushes, because most pushes change `openspec/changes/`. A pre-push docs check comes only when more than 3 failures of the `docs` row in a week come from stale pages.

## Considered Options

- **Build the generated documents at publish and commit none (Q12):** rejected. The owner keeps them visible on GitHub, and the brain reads them from `main`.
- **cogapp for the generated blocks:** rejected. cog runs Python from the documents. The generator already writes marker blocks.
- **A pre-push hook that runs the generator:** rejected. It runs on most pushes.

## Consequences

- A pull request that changes a command, an option, a setting, an error or a metric also changes its generated page. A conflict on a generated page goes away when the author runs the generator again after the rebase.
- The items of tracker #4880 build sections 1 to 4. Each item puts its spec delta in a nested capability `openspec/specs/project-brain/<area>/spec.md`, as ADR 0023 sets.
- The brain gets no key for document drift. Each run of `devops docs drift` reads the documents again.

## Status History

This record amends ADR 0023 and ADR 0012.

Amended on 2026-11-12 ([#5163](https://github.com/dan-petty/devops-cli/issues/5163)): the owner approved the held row of #4880. The command matrix moved from `README.md` into `docs/CLI_REFERENCE.md`, which is now a short generated index of the command group pages. `README.md` holds no generated block and links the index. `devops docs generate` regenerates the documents, and the option `--sync-readme` is deleted.

The merge of the pull request that adds this record is the approval of this record. `git log --follow -- docs/adr/0025-generated-documents-stay-in-git-and-the-project-brain-cites-them.md` names the merge commit.

- **ADR 0023.** Its note at the top names this record. Section 2 of this record adds the documents to the sources of the brain, as class C of ADR 0023 section 3. Section 3 of this record adds a lane for document drift, apart from the 2 insight proposals a week of ADR 0023.
- **ADR 0012.** ADR 0013 supersedes ADR 0012, and #4656 replaced its Pages item. The rest of decision 12 named an item that builds the reference pages at publish. That item does not come. Its note at the top names this record.
- **ADR 0014** stays as it is. The pre-push hook runs the fast static checks only, and no generator.
- **Q12** of 2026-10-22 does not apply to the generated documents.

2026-11-12: Fact out of date: the Pages workflow builds the site with Zensical from `docs/` and the root documents (#5183).

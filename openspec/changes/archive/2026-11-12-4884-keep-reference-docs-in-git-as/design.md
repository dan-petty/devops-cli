# Design

## Decisions

The decisions are in ADR 0025 (`docs/adr/0025-generated-documents-stay-in-git-and-the-project-brain-cites-them.md`). In short:

- **Generated documents stay in git.** They are marked `linguist-generated`, the pull request that changes their source regenerates them, and the `docs` row checks them. No item builds them at publish.
- **Documents are sources of the brain**, read from `main` through the RAG docs collection by their class in the docs inventory. An entry from a document is class C of ADR 0023: the document is its durable copy. Each entry holds one citation with a first-parent commit of `main`.
- **Document drift has its own lane:** at most 3 batch issues a week, apart from the 2 insight proposals of ADR 0023.
- **The precision rule:** a check runs at pull request time only when its run on `main` shows 0 false positives.
- **ADR 0014 stays:** the pre-push hook runs no generator.
- **The amended records keep their text.** ADR 0023 and ADR 0012 each get a note at their top, as ADR 0020, ADR 0021 and ADR 0022 have.
- **The record fits the ADR budget.** The status lines and the options of ADR 0025 are short, and the note of ADR 0023 names the record only. The ADRs in force use 8,183 of the 8,192 tokens that the alternatives check reads.

## Rejected alternatives

- **A spec delta for the `project-brain` capability, as the issue asks.** `openspec/config.yaml` gives a change that alters no observable behavior no spec delta. The citation and the drift lane are not built, so a requirement now would describe behavior that the code does not have, and no test under `tests/` can assert it. #4625 made the same choice for ADR 0023. #4921 and #4920 add the deltas with the code.
- **A longer note at the top of ADR 0023.** A note of one sentence more puts the ADRs in force at 8,206 tokens, and the alternatives check then leaves out ADR 0001.
- **New rows in the tables of ADR 0023.** The issue asks for a note only. ADR 0025 holds the change, and the note names it.
- **Edit decision 12 of ADR 0012.** An ADR is a record and keeps its text. The note at its top cancels the rest of decision 12, as the note of #4656 replaced its Pages item.

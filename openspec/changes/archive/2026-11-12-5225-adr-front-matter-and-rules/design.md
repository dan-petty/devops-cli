# Design

## Decisions

- **The front matter holds the status, and the body holds the decision.** MADR 4 puts the status in the front matter, so the parser reads a typed mapping and no prose. Each link key holds record numbers as quoted strings of four digits, and a strict string refuses an unquoted number, because YAML 1.1 reads `0017` as the octal 15.
- **The model refuses unknown keys.** `AdrFrontMatter` has `extra="forbid"` and validates the aliases only (`by_name=False`), so a key such as `superseded_by` fails and does not drop a link with no word.
- **An ADR in force is accepted, or has no status, and no ADR supersedes it.** Either record of a supersession can say so, as before, so a link in one direction in another repository still leaves the old record out. The invariant test asks for both directions in this repository.
- **The entry names the amending records, and no status prose.** The line `Amended by ADR 0021.` costs a few tokens. The prose that the records held is 1,121 tokens, and the alternatives check does not need it to find a rejected tool.
- **`## Status History` is the last section.** The intro paragraphs of records 0001 to 0017 have no heading, so a section after the title would hold them. At the end, a new line goes at the end of the file, and the body is the text before the section.
- **The body hash leaves out the target of each link.** The rules allow a fix of a broken link after acceptance, so the hash reads the type, the tag and the content of each markdown-it token and of each inline child, and no attribute. Every other edit changes the hash. The hash uses `hash_text` of `roadmap/body_hash.py`.
- **The rules live in `devops_cli/docs/adr_records.py`.** The roadmap reader stays the reader of the check. The docs module gives the index for `devops docs generate` (a synced block, as the grade table of the job success page) and the problems for the invariant test. The README is a hand-written page with a generated block, so the inventory of the documents lists only the numbered records as the class `record`.
- **The notes move word for word.** The notes at the top of a record and its `## Status` section move into the Status History in their order, and the new dated lines follow. ADR 0012 keeps its fourth top paragraph in the body, because it gives the reason of the decision. ADR 0007 keeps its section `Amendment (2026-10-24 ...)`, because it is a rule of the body.
- **A status icon for each record.** The theme draws an icon only for `new` and `deprecated`, and a filled square for any other status. `overrides/main.html` gives `proposed` the icon of `new`, `rejected` and `superseded` the icon of `deprecated`, and hides the icon of `accepted`, which most records have.

## Rejected alternatives

- **A hash of the raw text of the body**: rejected, because a fix of a broken link, which the rules allow, would then fail the test, and the test could not tell that fix from an edit.
- **A `## Status History` section after the title**: rejected, because the intro paragraphs of records 0001 to 0017 would fall into it, and a heading for them would edit the body.
- **Integer record numbers in the front matter**: rejected, because YAML reads `0017` as 15 with no error.
- **A generated `docs/adr/README.md` as a whole file**: rejected, because the README holds hand-written rules and a template, and the synced block of the grade table already does this for one page.
- **python-frontmatter**: rejected, because it is a new dependency, and mdit-py-plugins is already locked and parses the rest of the record.

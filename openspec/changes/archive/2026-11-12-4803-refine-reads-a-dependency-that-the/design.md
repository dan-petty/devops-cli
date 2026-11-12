# Design

## Decisions

- **An exact title, open first.** A quoted title names the one open Item with that exact title. With no open Item, it names the one closed Item with that title, because a delivered dependency holds nothing back but is still a dependency. Two Items with the title, or none, leave it unmatched.
- **Only a Conventional Commit title is a title.** Every roadmap item has a Conventional Commit title, so quoted text with no listed type, such as `"kilo"`, names no dependency.
- **A list item with `#N` is read by its number.** When a list item names `#N` and a title, the number names the issue. An old title beside the number then fails nothing.
- **An unmatched title is a job failure.** It is the check `dependencies` of `JobCheck`, so no person waits. The error asks for `#<number>`, and the round retries up to `CONST_ROADMAP_REFINE_MAX_TRIES`.
- **One reader for refine and stage.** `title_dependencies` serves both jobs. The stage job reads the listing once a run through a cached property of its judge.

## Rejected alternatives

- **Tell the model to resolve titles.** The model wrote "None" for #4574, which has 4 title dependencies, so the model does not do this step reliably. A deterministic match costs no tokens.
- **Match only open issues.** In the census, 13 of 57 titles name closed issues. A match on open issues only would fail 9 issues whose dependencies are already delivered.
- **A fuzzy title match.** A near match can link the wrong issue, and the wrong dependency blocks an item with no cause. An exact match, and `#N` when it fails, has no such risk.
- **Refuse every quoted text in the section.** Quoted text such as a tool name is no dependency, and a refusal would fail the round of a correct body.

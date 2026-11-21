# Proposal: #6613

## Why
Closes #6613. `body_dependencies` reads the Dependencies section of an item body up to the next heading of the same or a higher level. The alternatives job writes its block at the end of the body, often directly after the Dependencies section, with no heading between them. CommonMark ends the HTML comment of the start marker at the end of its line, so the "Covers" and "Lacks" lines of the block parse as blocks of the Dependencies section. Each `#N` in them then names a blocker, but the alternatives text names tools, not blockers. A false blocker keeps an item away from the jobs for too long. On 2026-11-21, 2 of the 812 open items gave a different blocker list with the alternatives block removed: #4568 gets #5506 from its Lacks line "Two-container template integration that #5506 adds".

## What Changes
- `_section_tokens` in `src/devops_cli/roadmap/refine/refine.py` ends a section at the next heading of the same or a higher level, or at an HTML block that is the start or the end marker of a job block, whichever comes first. The four marker constants give the set of markers. A heading inside a job block still starts a section, so the `### Dependencies` part that refine writes in its own block still names its blockers.
- The three readers that use `_section_tokens` get the rule: `body_dependencies`, `body_questions` and the quoted titles of `title_dependencies`.
- `CONST_ROADMAP_REFINE_RULES_SINCE` gets a later time, because the change removes false dependencies from a rule that sets a next step (the convention in the comment of the constant, as #6451 did).
- The change alters what refine and the jobs read as blockers and as key questions. That is observable, so the change carries spec deltas.
- The change fits one pull request.

## Capabilities
- `roadmap-refine/waits`: ADDED requirement "A job block marker ends the Dependencies section".
- `roadmap-refine/proposal`: MODIFIED requirement "The body's answered key questions are not asked again", because its text states the old end of the section.

## Impact
- Refine, the stage job and the implement job read no blocker from the alternatives block. #4568 loses the false blocker #5506 at its next refine round.
- The refine record of an item keeps its old `refine.blocked_by` until the next refine round. The change does no data migration.
- `docs/roadmap/refine.md` states the end of the Dependencies section and the new version of the rules.

## Feasibility
- Code: `_section_tokens` at `src/devops_cli/roadmap/refine/refine.py:1163` on origin/main `c6395d856` ends a section only at a `heading_open` token.
- Parser: markdown-it-py 4.3.0 (`MarkdownIt("commonmark")`) gives each marker line as its own `html_block` token whose stripped content is the marker, also directly after a paragraph or a list item with no blank line. A marker in a code span or inside a paragraph is part of an `inline` token, so it ends no section.
- Base output: `body_dependencies` gives `[5506]` for `## Dependencies`, `None.`, and then an alternatives block whose Lacks line names `#5506`. It gives `[4989, 5506]` for the refine `### Dependencies` part `- #4989` when the alternatives block follows the refine end marker.
- Set counts: `git grep -c 'devops-roadmap-[a-z]*:\(start\|end\) -->"' -- src/devops_cli/config/constants.py` gives 4 markers (refine and alternatives, start and end). `grep -n "_section_tokens(" src/devops_cli/roadmap/refine/refine.py` gives 3 callers. The record marker `devops-roadmap-record` has no start or end form, and the store removes it from each body that it reads.

## Existing Tool Considered
- markdown-it-py (MIT, maintained, last activity 2026-11-10) is already the parser of the body. It gives the `html_block` token, but it has no rule that ends a section at a marker of this project. The alternatives check of the issue found no tool that knows the job block markers (verdict `none`).
- Build cost: about 10 lines of code and 5 tests; about 20k tokens and 30 minutes to build, and a low cost to keep, because the rule uses the token that the parser already gives.
- The change deletes no internal code: it adds one end condition to `_section_tokens`.

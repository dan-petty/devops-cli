# Design

## Decisions
- **Guidance, not a cap.** The prompt asks for a brief reply. The schema sets no length, so a long reply passes and the job writes it whole. A cap would make a check fail, or drop context that refine, stage and implement read (owner, 2026-11-17).
- **Fold, do not cut.** The tools considered, the searches and the sources go into one `<details>` block. Its summary counts the answered searches. The block holds every line that the comment held before, so a reader of the comment text loses nothing.
- **One tool line.** The comment uses the tool line of the block of the body (`_tool_line`), so the comment and the block state the same facts in the same form.
- **Machine-read lines stay.** The marker, the heading, `Reason:`, `Covers:`, `Lacks:` and `Tool: none found` stay. The block of the body does not change.
- **The source bound stays.** The comment keeps its bound of `CONST_ROADMAP_ALTERNATIVES_MAX_COMMENT_SOURCES` sources and its line that counts the rest, as before this change.

## Rejected alternatives
- **Length limits in the schema of the reply**, with one retry for a longer reply: the owner refused hard caps that make a job fail or miss context (2026-11-17).
- **A character cap in the render**: it cuts text that other jobs read.
- **No tools considered and no searches in the comment**: they are the evidence of a `none` verdict, and #2944 added them on purpose.

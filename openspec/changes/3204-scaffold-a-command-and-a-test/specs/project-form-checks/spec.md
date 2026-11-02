## Purpose
Which of the checks that guard a new command or a new docs page compute their lists from the command tree and the docs folder, so that a new file needs no hand edit and a stale entry fails the check.

## ADDED Requirements

### Requirement: The MCP coverage test derives the excluded commands
The MCP coverage test SHALL derive the excluded commands as every command of the tree that `CONST_MCP_EXPOSURE_TABLE` does not name, and SHALL fail when an exposure entry names no command of the tree.

#### Scenario: A new command needs no exclusion entry
- **WHEN** A command joins the command tree and no exclusion entry is added.
- **THEN** The MCP coverage test passes, and an exposure entry that names no command fails it.

### Requirement: An unmatched docs page is hand-written
`CONST_DOCS_INVENTORY` SHALL classify a Markdown file that no other class of the inventory matches as hand-written, with no per-file entry.

#### Scenario: A new hand-written page needs no inventory entry
- **WHEN** A page is added at a docs path that no other class matches.
- **THEN** The docs inventory check passes with no change to `CONST_DOCS_INVENTORY`.

### Requirement: The test document states the mirror rule as the only rule
The layout section of `docs/TESTING.md` SHALL state that a new test module sits at the mirror path of its source module, and SHALL state no flat-file fallback for a new test.

#### Scenario: The layout section states one rule
- **WHEN** A reader opens the layout section of `docs/TESTING.md`.
- **THEN** The section names the mirror path and holds no instruction to add a new flat test file.

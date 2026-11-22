# Proposal

## Why

`with_record` writes the job record block as a comment after the body, and `split_record` reads it only when CommonMark parses it as the last block of the body (#2630). The body can end inside a fenced code block or an HTML block, such as a comment or `<pre>`, that it does not close. Then the record comment becomes part of that block (#6729). So the read gives an empty record and a body that holds the old block. In a fence, GitHub shows the record text as code. Each later write adds one more record to the body. The GitHub store also reads no mark back, so it writes two more times and raises `RoadmapRecordMarkLostError`.

## What Changes

- `with_record` closes a fenced code block or an HTML block that the body leaves open at its end, with `close_open_block` of `src/devops_cli/roadmap/body_hash.py` (#6627), before it adds the record block. The new function `closed_body` of `store.py` gives the body with the close. The close takes the place of one line break at the end of the body, so the code of the block gets no new empty line.
- A body that leaves no block open is written with the same text as before.
- `split_record` gives back the body with the close. The docstrings of `with_record` and `split_record` say this.
- `_edit_issue` of the GitHub store compares the body that it reads back with `closed_body` of the body that it wrote. Its first check also accepts `closed_body` of the body of the Item, because an earlier write from the same read can add the close. Thus the close is no edit of a person, and `devops_cli_roadmap_record_lost_edit_total` does not count it.
- `docs/ROADMAP_WORKFLOW.md` says that a record write closes an open block.
- The spec delta adds one requirement to `roadmap-item-labels`, because the body that a read gives and the record that a write keeps are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-item-labels`: A record write closes the block that the body leaves open

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/stores/test_roadmap_store_record_block.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`, `tests/roadmap/stores/test_roadmap_github_store_record_writes.py`
- A body that ends in an open block gets one close line at its first record write. The body hash of that body changes one time, so refine or alternatives can run one more round on it. The next write keeps the body.

## Feasibility

- A scratch script on origin/main `a3e30286e` (2026-11-22) writes a record with `with_record` and reads it with `split_record`. A closed fence gives the record back. An open backtick fence, an open tilde fence, an open `<!--` and an open `<pre>` each give `{}`, and a second write makes the body longer.
- `close_open_block` (`src/devops_cli/roadmap/body_hash.py`) parses the text and a probe comment after a blank line with markdown-it-py, and adds the close of the open fence or of the HTML block of CommonMark kinds 1 to 5. The record block is a one-line comment after a blank line, as the probe is, so the same parse decides both.
- `body_hash.py` imports `Item` and `RefineRecordKey` from `store.py`, so `store.py` imports `close_open_block` inside `closed_body`. The invariant of `tests/invariants/test_architectural_invariants.py` accepts an import inside a function (#848), and `get_roadmap_store` already imports `github_store` that way.
- A CommonMark render with markdown-it-py gives the same HTML for a fence that the body leaves open at the end and for the closed fence, when the close takes the place of one line break at the end.

## Existing Tool Considered

markdown-it-py parses the body, and the change uses it through `close_open_block` of #6627. No tool adds a record block to a Markdown body or reads one back. The change builds no parser: about 50 changed lines of source, about 40k tokens and about 2 hours. It deletes no code.

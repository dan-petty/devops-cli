# Proposal: #4445

## Why

Closes #4445. Each `devops roadmap intake` run lists every issue and pull request of the repository, 4,431 entries on 2026-11-11. The store turns each entry into an `IssueRecord`, and `split_record` parses each body with markdown-it to find the job record block at its end. In three profiled `--plan` runs of #4404, this parse took 92 s, 68 s and 140 s (the last one under cProfile), and the whole run took 5 to 6.5 minutes.

Two parts of this work give no result:

- Only 1,084 of the 4,431 bodies hold the opening text of the record block, `<!-- devops-roadmap-record `. A body without it can have no record block, but the store parses it fully.
- The parser runs the inline rules of each body, but `_record_block_span` reads only the top-level block tokens (`level`, `type` and `map`).

## What Changes

- `split_record` returns the body and an empty record, with no parse, when the body does not hold the opening text of the record block.
- The Markdown parser of the store, `_BODY_MARKDOWN`, turns off the core rule `inline` of markdown-it, so it parses only the blocks.

The result of `split_record` does not change for any body. The change makes the read of a listing faster and alters no behavior that a consumer observes. So it has no spec delta, and `.openspec.yaml` sets `skip_specs: true`.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/roadmap/stores/store.py`: the fast path of `split_record` and the block-only parser.
- Every reader of the issue listing gets the speed-up: intake on the CLI and in the Service, and every other job that reads `GitHubRoadmapStore.issues`.
- No document describes the parse, so no document changes.

## Feasibility

I confirmed the premise on 2026-11-11 against the real repository, with markdown-it-py 4.2.0 of `uv.lock`:

- Three `devops roadmap intake --plan` runs under a timing harness (#4404) gave a body parse of 92 s, 68 s and 140 s. The host had a load average of about 67, so the wall time is longer than the CPU time.
- One copy of the 4,431 bodies of the listing, read through `GitHubRoadmapStore.issues`, has 1,084 bodies that hold the opening text and 1,082 bodies that hold a record block.
- On that copy, `split_record` of the base takes 21.7 s, 23.0 s and 18.1 s of CPU time in three runs, and `split_record` of this change takes 6.4 s, 6.1 s and 5.0 s. The JSON of the 4,431 results is the same byte for byte (SHA-256 `b36ea2db36b5d636…`).
- `_RECORD_BLOCK` is a full match that starts with the opening text, so a body without that text can give no record. The core rule `inline` of markdown-it fills only the `children` of the `inline` tokens. The block parser makes the type, the level and the line map of each top-level token, and CommonMark lets an HTML comment interrupt a paragraph, so the block structure does not depend on the inline rules.

## Existing Tool Considered

markdown-it-py is already the parser of the store. `MarkdownIt.disable("inline")` is its public API to turn off one core rule. The change adds no library and no helper. Cost: about 15,000 tokens to build, about 1,000 tokens a year to keep, and about 1 hour of elapsed time.

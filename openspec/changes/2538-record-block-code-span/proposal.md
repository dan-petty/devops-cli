# Proposal

## Why

Issue #2538: `split_record` in `src/devops_cli/roadmap/store.py` finds the job record with a regular expression anywhere in the issue body.
The expression does not know Markdown.
Text that only quotes the record format in a code span or a code block is read as the record block.
The read gives an empty record and a warning, and the body that it returns no longer holds the quote.
The next write of the record then deletes the text that a person wrote.

## What Changes

- `split_record` parses the body with markdown-it-py. Only the last block of the body counts as the record block, and only when it is an `html_block` that holds the record comment.
- A quote in a code span, a fenced code block or an indented code block stays in the body. A record comment that more text follows is not the record.
- The removal of the record block takes out that block only. The regular-expression substitution that removed every match is deleted.
- Tests in `tests/test_roadmap_store_contract.py` cover both store adapters.
- The requirement "The issue body holds the job record" of `roadmap-item-labels` states the rule.

## Capabilities

### Modified Capabilities

- `roadmap-item-labels`: the job record is the comment at the end of the issue body. A quote of the record format elsewhere in the body is text, and is kept.

## Impact

- `src/devops_cli/roadmap/store.py`
- `tests/test_roadmap_store_contract.py`
- `openspec/specs/roadmap-item-labels/spec.md`

The change fits one pull request.

## Feasibility

- **Token types**: markdown-it-py (the version that `uv.lock` pins) with the `commonmark` preset gives an `html_block` token for a comment that starts a line, and a `code_inline`, `fence` or `code_block` token for a quote.
  The new tests assert this for a code span, a fence, an indented code block and a comment in the middle of the body.
- **Block lines**: a token has `map`, its first line and the line after its last. The code turns these lines into offsets of the original text, with the same line breaks (`\r\n`, `\r`, `\n`) that markdown-it-py reads.

## Existing Tool Considered

markdown-it-py, which `refine.py` already uses for the same Markdown that GitHub shows.
Rejected: a regular expression that skips code spans. It cannot find the boundaries of all code spans and code blocks, and it copies the parser.
The change deletes `_RECORD_BLOCK.sub`, the removal of every match.

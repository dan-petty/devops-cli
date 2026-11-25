# Proposal: #6535

## Why
Roadmap body readers build a new CommonMark parser on each call.
Building a parser takes about 0.40 ms while parsing a short section takes about 0.07 ms.
The parser construction accounts for approximately 85% of the execution time for short parses.
Reusing one cached parser significantly reduces execution time during dependency graph and body reads.

## What Changes
Provide a cached factory `commonmark_parser()` in `src/devops_cli/roadmap/markdown.py`.
Update roadmap readers in `refine.py`, `stage_criteria.py`, and `step_files.py` to use `commonmark_parser()`.
Prevent new parser constructions on each read operation.

## Capabilities
A shared cached CommonMark parser factory for roadmap readers.
Performance improvement for roadmap dependency graph and body reading operations.

## Impact
Fewer object allocations and faster roadmap operations.
No changes to public CLI commands or external interfaces.

## Feasibility
Verified that `MarkdownIt("commonmark")` parser instances are safe to reuse across multiple parses.
Verified call sites in `refine.py`, `stage_criteria.py`, and `step_files.py`.

## Existing Tool Considered
The alternatives check in issue #6535 records `not-applicable` for performance class.
The change uses `markdown-it-py` from `uv.lock`.

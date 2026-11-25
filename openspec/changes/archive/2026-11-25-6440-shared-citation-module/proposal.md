# Proposal: #6440

## Why

PR #5040 delivered only the stage-gate citation rule inside `src/devops_cli/roadmap/stage/stage_change.py`, leaving citation patterns and anchoring private and unshared. Neither `stage_change`, the question resolver (#4808), brain add (#4671), nor brain repair (#4687) shares one typed module that parses ADR 0025 structured citations, verifies commits without unnecessary GitHub requests, or re-anchors unique moved spans. Closes #6440.

## What Changes

- Add top-level module `src/devops_cli/citation.py` so both `devops_cli.roadmap.stage` and `devops_cli.ai` import it with zero cross-dependency between `roadmap` and `ai`.
- Provide frozen dataclasses (`LineCitation`, `SymbolCitation`, `StructuredCitation`, `ReanchorResult`, `VerificationResult`) and public functions to compute `span_hash`, parse all three citation forms, extract inline citations, verify at a commit (local `git` first with 0 GitHub requests, remote fallback only when the commit is absent locally), re-anchor a stale span only on 1 match (refusing 0 or 2+ matches), and render commit permalinks.
- Refactor `src/devops_cli/roadmap/stage/stage_change.py` to delegate citation parsing, symbol checks, and line re-anchoring to `devops_cli.citation`, removing `_LINE_CITATION`, `_SYMBOL_CITATION`, `_anchored_line`, and `_line_citation` while keeping every gate result and message identical.

## Capabilities

### New Capabilities

- `project-brain/citation`: Shared citation types, SHA-256 span digest, local-git-first commit verification, unique-match re-anchoring, and permalink rendering across line, symbol, and ADR 0025 structured citations.

### Modified Capabilities

- None (`roadmap-plan-check` behavior, messages, and log outputs remain unchanged).

## Impact

- Code: `src/devops_cli/citation.py` (new), `src/devops_cli/roadmap/stage/stage_change.py`
- Tests: `tests/core/test_citation.py` (new), `tests/roadmap/stage/test_roadmap_stage_content.py`
- Downstream follow-ups (#4808, #4671, #4687) to be notified after merge.

## Feasibility

- `src/devops_cli/roadmap/stage/stage_change.py` currently holds the existing private citation logic (`_LINE_CITATION`, `_SYMBOL_CITATION`, `_anchored_line`, `_line_citation`), and `src/devops_cli/ai/kb.py` already computes 16-char SHA-256 prefixes using `CONST_KB_SHA_DIGEST_LENGTH` (`src/devops_cli/config/constants.py`).
- Existing `src/devops_cli/core/process.py` (`run_subprocess`) lets `citation.py` execute `git cat-file` and `git show` with zero circular imports between `ai` and `roadmap`.

## Existing Tool Considered

No open library parses this project's `path:line:text`, `path:def name`, and ADR 0025 structured citation schema, verifies against a local git commit before falling back to one contents GET, or re-anchors only unique span matches. The change moves existing repository code into `src/devops_cli/citation.py` (~180 lines) using stdlib `hashlib`, `re`, `dataclasses`, and existing `run_subprocess` / `CONST_KB_SHA_DIGEST_LENGTH`. Estimated cost: ~40k tokens and ~1 hour.

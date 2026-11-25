# project-brain/citation Specification

## Purpose

Define the shared `devops_cli.citation` module for parsing line, symbol, and ADR 0025 structured citations, hashing cited spans, verifying commits via local git before falling back to one remote fetch, uniquely re-anchoring moved spans, and delegating stage gate checks without duplicating pattern or anchor logic.

## ADDED Requirements

### Requirement: One parse function for three citation forms
`devops_cli.citation.parse_citation` SHALL accept a line citation (`path:line:text`), a symbol citation (`path:def name` or `path:class name`), and an ADR 0025 structured mapping (`path`, `commit`, `lines`, `span_hash`, `doc_class`, optional `generated_from`, `adr_status`, `as_of`), returning a typed frozen dataclass instance.

#### Scenario: Parse line, symbol, and structured forms
- **WHEN** callers pass a `path:line:text` string, a `path:def symbol` string, and an ADR 0025 mapping to `parse_citation`
- **THEN** each call returns `LineCitation`, `SymbolCitation`, or `StructuredCitation` carrying the exact path, line or symbol, commit, line range, `span_hash`, and `doc_class` / `adr_status` fields.

### Requirement: Span hash matches knowledge base hash
`devops_cli.citation.span_hash` MUST return the first `CONST_KB_SHA_DIGEST_LENGTH` (16) lowercase hexadecimal characters of the UTF-8 SHA-256 digest of the input text.

#### Scenario: Equal 16-hex span hash
- **WHEN** `span_hash(text)` runs on a span string
- **THEN** the return value equals `hashlib.sha256(text.encode("utf-8")).hexdigest()[:CONST_KB_SHA_DIGEST_LENGTH]`.

### Requirement: Local commit verification sends no remote request
`devops_cli.citation.read_at_commit` and `verify_citation` SHALL read `<commit>:<path>` via local git when the commit exists in the clone and MUST NOT invoke the remote contents callback in that case. When the commit is absent locally and a remote callback is given, they MUST invoke the callback at most once.

#### Scenario: Local commit uses zero requests and missing commit uses one
- **WHEN** `read_at_commit` runs for a commit present in local git with a raising remote callback, then runs for an absent commit with a recording callback
- **THEN** the local lookup reads the content with zero callback calls and the missing-commit lookup invokes the callback once.

### Requirement: Re-anchor only a unique span match
`devops_cli.citation.reanchor_span` SHALL keep the expected line range when it matches, SHALL move the range only when the normalized span occurs once in the file (`re_anchored=True`), and MUST refuse with a reason when the span matches zero times or two or more times.

#### Scenario: One match moves while zero and multiple matches refuse
- **WHEN** a moved span occurs once, zero times, or twice in target content
- **THEN** `reanchor_span` returns the new line range for one match and returns a non-matching `ReanchorResult` naming the mismatch count for zero and two matches.

### Requirement: Permalink rendering at commit and stage gate delegation
`devops_cli.citation.render_permalink` SHALL format a GitHub blob permalink naming the commit, repository path, and `#L<start>` / `#L<start>-L<end>`. `src/devops_cli/roadmap/stage/stage_change.py` SHALL delegate to `devops_cli.citation` and MUST define no `_LINE_CITATION`, `_SYMBOL_CITATION`, `_anchored_line`, or `_line_citation`.

#### Scenario: Stage gate delegates without private citation attributes
- **WHEN** `stage_change` checks a proposal while public `devops_cli.citation` parse and re-anchor functions are wrapped
- **THEN** `stage_change` has none of `_LINE_CITATION`, `_SYMBOL_CITATION`, `_anchored_line`, `_line_citation`, invokes `devops_cli.citation` functions, and produces identical gate findings and log messages.

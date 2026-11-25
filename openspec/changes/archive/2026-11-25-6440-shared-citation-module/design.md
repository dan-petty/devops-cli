# Design

## Decisions

- **Top-level `src/devops_cli/citation.py`**: Putting the shared module at the top level avoids coupling `devops_cli.ai` and `devops_cli.roadmap.stage`. `citation.py` imports only `config.constants`, `core.process`, and standard library modules (`dataclasses`, `hashlib`, `re`, `pathlib`).
- **Typed frozen dataclasses**: Represent each parsed citation (`LineCitation`, `SymbolCitation`, `StructuredCitation`), re-anchoring outcome (`ReanchorResult`), and commit verification outcome (`VerificationResult`) as frozen dataclasses with explicit fields.
- **Span hash**: Compute `hashlib.sha256(text.encode("utf-8")).hexdigest()[:CONST_KB_SHA_DIGEST_LENGTH]` (16 hex characters), matching `src/devops_cli/ai/kb.py`.
- **Verification**: Check `git cat-file -e <commit>^{commit}` locally first. When the commit exists locally, read `<commit>:<path>` via `git show` and make zero remote calls even when `<path>` is absent in that commit. Only when the commit is missing from the local clone does `read_at_commit` call the optional single-file contents callback once.
- **Re-anchoring**: Normalize lines with `squash_whitespace` and accept either an exact expected line match or a single unique match across the file (`len(matches) == 1`); return `matched=False` with an explicit count reason for zero or multiple matches.
- **Stage gate delegation**: Import `devops_cli.citation as citation` in `src/devops_cli/roadmap/stage/stage_change.py` and invoke its public functions (`parse_citation`, `extract_citations`, `reanchor_span`, `defines_symbol`, `quoted_line_text`) while removing `_LINE_CITATION`, `_SYMBOL_CITATION`, `_anchored_line`, and `_line_citation`. Keep `doc_class` and `adr_status` as plain unvalidated strings so `citation.py` stays decoupled from `docs.inventory` and `roadmap.adr`.

## Rejected alternatives

- Placing citations under `src/devops_cli/roadmap/stage/` (rejected: forces `devops_cli.ai` to import from `roadmap.stage`).
- Using plain dicts or Pydantic models (rejected: loses field safety vs dataclasses or adds validation overhead).
- Querying GitHub contents API first or reading only the working tree (rejected: burns rate limit or masks stale commit citations).
- Re-anchoring via fuzzy match or first occurrence (rejected: risks citing unrelated text).

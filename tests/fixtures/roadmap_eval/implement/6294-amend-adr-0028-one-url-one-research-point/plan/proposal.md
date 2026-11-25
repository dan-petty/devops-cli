# Proposal: #6294

## Why

ADR 0028, section 1, says "A fetch writes one point for each `source_url` and `content_hash`" and "a new hash replaces the text and keeps the URL". The two halves disagree about a new hash, and the plan for #3906 must build one of them (#6294). An agent never edits the body of an accepted record, so the rule goes into the Status History of the record, which the rules allow.

## What Changes

- Add one dated line to the Status History of `docs/adr/0028-a-research-agent-composes-open-tools-and-a-research-index.md`. It says that the index keeps one point for each `source_url`: the same hash updates `fetch_date` and `expiry`, and a new hash replaces the text and the `content_hash` of that point. The body does not change.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/adr/0028-a-research-agent-composes-open-tools-and-a-research-index.md`

## Feasibility

- `docs/adr/0028-a-research-agent-composes-open-tools-and-a-research-index.md`, section 1, holds both sentences: `A fetch writes one point for each source_url and content_hash; the same hash updates fetch_date and expiry, and a new hash replaces the text and keeps the URL.`
- `docs/adr/README.md`, section `An accepted record does not change`, allows one dated line at the end of Status History, and says `An agent never edits the body of an accepted record.` `docs/adr/0001-github-is-the-roadmap-source.md` holds a dated correction line in its Status History with no new record: `2026-11-12: Fact out of date: labels hold the Item fields, not board fields`.
- `tests/invariants/test_adr_records.py` computes the hash of the body again, and the Status History is not part of the body, so the line changes no hash and no index row.

## Existing Tool Considered

The ADR rules of `docs/adr/README.md`: one dated Status History line. No other tool applies, and no new record is needed, because the decision does not change: the line says which reading of ADR 0028 holds. The work is about 1k tokens and a few minutes.

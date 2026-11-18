# Tasks

## 1. Clarify ADR 0028 in its Status History

Kind: other. Reads: `docs/adr/README.md`, `docs/adr/0001-github-is-the-roadmap-source.md`, `tests/invariants/test_adr_records.py`. Changes: `docs/adr/0028-a-research-agent-composes-open-tools-and-a-research-index.md`.

- [x] 1.1 Add one dated line at the end of the Status History of `docs/adr/0028-a-research-agent-composes-open-tools-and-a-research-index.md`: the index keeps one point for each `source_url`, the same hash updates `fetch_date` and `expiry`, and a new hash replaces the text and the `content_hash` of that point
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

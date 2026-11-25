### Problem

ADR 0028, section 1, says two things about a fetch that cannot both hold. It says "A fetch writes one point for each `source_url` and `content_hash`", and it says "a new hash replaces the text and keeps the URL". The first gives a second point for a new hash. The second gives one point for each URL. The plan for #3906 must pick one, and a reader of the ADR cannot tell which one the owner meant.

### Expected

One dated line at the end of the Status History of ADR 0028 that states the rule: the research index holds one point for each `source_url`. The same hash updates `fetch_date` and `expiry`. A new hash replaces the text and the `content_hash` of that point. An agent never edits the body of an accepted record, so the body of ADR 0028 does not change, and no new record is needed: the decision does not change, the line only says which reading of the sentence holds.

### Acceptance criteria

- ADR 0028 has one new dated Status History line that states one point for each `source_url`, and names the same-hash and new-hash cases.
- The body of ADR 0028 is unchanged, and `uv run devops ci test tests/invariants/test_adr_records.py` passes.

### Existing tool considered

The ADR rules of `docs/adr/README.md`: one dated Status History line, as `docs/adr/0001-github-is-the-roadmap-source.md` shows. No other tool applies.

### Related

Related: #3877 (delivered ADR 0028), #3906 (its plan reads the rule).


<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->

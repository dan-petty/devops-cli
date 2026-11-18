# Design

## Decisions

- **Add one dated Status History line, and no new record.**: The rules allow the line, ADR 0001 shows the same kind of correction line, and a new record is for a decision that changes. This line states which reading of an existing sentence holds.
- **Keep one point for each `source_url`.**: The sentence of ADR 0028 says a new hash replaces the text, and an index that answers from fetched pages must not hold two texts of one URL.
- **Leave the body of ADR 0028 as it is.**: The rules forbid an edit of the body by an agent, and the test compares the hash of the body.

## Rejected alternatives

- **A new record that amends ADR 0028.**: It adds a record, an `amended-by` key, an index row and a hash for one clarification, and no decision changes.
- **Edit the sentence in ADR 0028.**: The rules forbid it for an agent, and the body-hash test would fail.
- **One point for each `source_url` and `content_hash`.**: Each version of a page would stay, and a search could return an old text beside the new one.

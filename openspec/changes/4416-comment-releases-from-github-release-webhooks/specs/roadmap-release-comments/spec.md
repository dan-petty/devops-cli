## ADDED Requirements

### Requirement: A published release delivery comments at once
A `release` `published` delivery SHALL run the update scoped to it on the lane of the `release_comments` row before the next round of the row. The update SHALL build its release from the delivery, post `Released in <tag>` once on each closed issue of the release, and set the `released` flag of the tag in the ledger `release_comments.json`. It SHALL post no `Live since <time>` comment.

#### Scenario: The scoped update comments the closed issue
- **WHEN** a test runs the scoped `release` update with a fake store, the release tag `v1.2.3` and a release body that names issue 123
- **THEN** issue 123 holds one comment whose first line is the `released` marker of `v1.2.3`, and the ledger `release_comments.json` holds `released` true for `v1.2.3`

#### Scenario: A second delivery posts no comment
- **WHEN** a test runs the scoped `release` update twice for the tag `v1.2.3` with a fake store
- **THEN** issue 123 holds one comment whose first line is the `released` marker, and the ledger `release_comments.json` holds `released` true for `v1.2.3`

#### Scenario: The scoped update posts only the released marker
- **WHEN** a test runs the scoped `release` update for a published release
- **THEN** the fake store holds no comment whose first line is the `live` marker

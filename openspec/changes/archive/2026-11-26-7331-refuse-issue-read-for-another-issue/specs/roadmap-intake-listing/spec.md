## ADDED Requirements

### Requirement: A number that is no issue of the repository leaves the listing
When GitHub answers a read of a number with status 404 or with an answer that names another issue, the store SHALL take the record of that number out of its listing. When the listing of the store held the record, `IncrementalListing` SHALL leave the record out of each later read of the repository and out of the snapshot that the read keeps.

#### Scenario: A round drops the record of a redirected read
- **WHEN** the snapshot of a lane holds the open items 7 and 8, GitHub does not list issue 7 as changed and answers the read of issue 7 with issue 12 of another repository, and a round of the lane reads item 7 by its number
- **THEN** the read returns None, the store of that round lists item 8 only, the store of the next round lists item 8 only, and the snapshot that the next round keeps holds issue 8 only

#### Scenario: A read with status 404
- **WHEN** the snapshot of a lane holds the open items 7 and 8, and GitHub answers the read of issue 7 with status 404
- **THEN** the read returns None, and the store of that round and of the next round lists item 8 only

### Requirement: A dropped number stays out until GitHub lists it
`IncrementalListing` SHALL leave out the record of a dropped number whichever copy of the snapshot a read starts from. The number SHALL stay out until GitHub lists it as changed or until the next full read.

#### Scenario: Another copy of the snapshot holds the record
- **WHEN** a round of a lane dropped the record of issue 7, and the snapshot store then gives a copy that holds issue 7 again
- **THEN** the store of the next round of that lane lists item 8 only

#### Scenario: GitHub lists the number again
- **WHEN** a round of a lane dropped the record of issue 7, and GitHub then lists issue 7 as changed since the watermark
- **THEN** the store of the next round lists the items 7 and 8

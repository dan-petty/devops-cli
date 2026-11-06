## Purpose
The shortlists of the consolidation job of the roadmap: for each open item, the other open items that may share its root cause, with the evidence for each, found by tools before any model call. It also covers the one nearest-item function that intake and the job share, and the cache of embeddings.

## ADDED Requirements

### Requirement: Intake and the job share one nearest-item function
The roadmap SHALL rank items by the cosine similarity of their embeddings in one function, `nearest`, and intake SHALL call it to build its shortlist.

#### Scenario: The closest vectors come first
- **WHEN** `nearest` ranks three vectors against a query and a limit of 2
- **THEN** it returns the keys of the two closest vectors, closest first
- **AND** keys with an equal score keep the order of the input

#### Scenario: Intake shortlists as before
- **WHEN** intake decides a candidate against a set of items
- **THEN** the shortlist that the model sees holds the same items in the same order as before the change

### Requirement: A shortlist is built from tools before any model call
For each open item as an anchor, the job SHALL list the other open items that cite the same path, cite the same identifier, link to the anchor, or are among its nearest items by embedding, and SHALL keep the evidence for each member. The build SHALL make no call to a language model.

#### Scenario: A shared path
- **WHEN** two open item bodies both cite `src/devops_cli/roadmap/store.py:100`
- **THEN** each is a member of the shortlist of the other, with the evidence "shared path"

#### Scenario: A shared path and a shared identifier
- **WHEN** two open items cite the same path and the same identifier in backticks
- **THEN** the evidence of the member is "shared path and identifier"

#### Scenario: A citation that many items share
- **WHEN** more open items than `DEFAULT_ROADMAP_CONSOLIDATE_COMMON_CITATION` cite one path
- **THEN** that path makes no member

#### Scenario: Links
- **WHEN** an item is blocked by another, is the sub-issue of another, or names another after "Depends on", "Related", "Split off" or "Merged into"
- **THEN** the other item is a member of its shortlist, with the evidence "link"
- **AND** a number under a nested bullet of such a line counts too

#### Scenario: Only open items
- **WHEN** a body names a closed issue or a pull request
- **THEN** that number is no member

#### Scenario: The nearest items by embedding
- **WHEN** an item has no citation and no link in common with any other item
- **THEN** its shortlist holds its `DEFAULT_ROADMAP_INTAKE_SHORTLIST` nearest items by embedding, with the evidence "embedding rank" and the rank

#### Scenario: No model call
- **WHEN** the shortlists are built with a fake embedder and no language model
- **THEN** the only calls are to the embedder and the store reads

#### Scenario: The length of a shortlist
- **WHEN** an anchor has more members than `DEFAULT_ROADMAP_CONSOLIDATE_MEMBERS`
- **THEN** the shortlist keeps the members with the strongest evidence, and a tie goes to the lower number

### Requirement: An item is in one group at most
The job SHALL place each item in one group at most, as the anchor or as a member. When two anchors both shortlist one item, the item SHALL join the anchor with the stronger evidence, and on equal evidence the anchor with the lower number. A member SHALL NOT anchor a group, and the job SHALL make no transitive join of shortlists.

#### Scenario: The stronger evidence wins
- **WHEN** anchor 9 shares a path and an identifier with an item, and anchor 4 only has the item among its nearest items
- **THEN** the item joins anchor 9

#### Scenario: A tie goes to the lower number
- **WHEN** two anchors have the same evidence for an item
- **THEN** the item joins the lower number

#### Scenario: A nearer embedding rank is stronger
- **WHEN** two anchors have only an embedding rank for an item, rank 3 and rank 1
- **THEN** the item joins the anchor with rank 1

#### Scenario: A pair is one group
- **WHEN** item A lists item B and item B lists item A with the same evidence
- **THEN** one group holds A as the anchor and B as a member
- **AND** B anchors no group

#### Scenario: No transitive join
- **WHEN** item B is in the shortlist of A, and item C is in the shortlist of B only
- **THEN** C is not in the group of A

#### Scenario: Equal input gives equal groups
- **WHEN** the same issues are listed in another order
- **THEN** the groups are the same

### Requirement: Embeddings are cached by the hash of the text
The job SHALL keep the embedding of each item in the data directory, keyed by the hash of its title and of its body outside the sections of the refine job and the alternatives job.

#### Scenario: An unchanged board embeds nothing
- **WHEN** the shortlists are built twice over the same issues
- **THEN** the second run makes no call to the embedder

#### Scenario: An edit embeds one item
- **WHEN** a person edits the body of one item between two runs
- **THEN** the second run embeds that one item

#### Scenario: A section of a job is no edit
- **WHEN** the refine job writes its section into a body between two runs
- **THEN** the second run makes no call to the embedder

#### Scenario: A different model
- **WHEN** the model name of the embedder changes between two runs
- **THEN** the second run embeds every item again

### Requirement: The store reads blocked-by links
The roadmap store SHALL return the numbers of the issues that block an issue, and the listing of issues SHALL carry the count of those blockers.

#### Scenario: The GitHub store reads the endpoint
- **WHEN** issue 3 is blocked by issue 1
- **THEN** `blocked_by(3)` returns `[1]` for the GitHub store and for the in-memory store
- **AND** the record of issue 3 in the issue listing holds a count of 1

#### Scenario: An issue with no blocker
- **WHEN** an issue has no blocker
- **THEN** the store answers `[]`, and the job makes no request for that issue

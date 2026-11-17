## ADDED Requirements

### Requirement: The first plan request holds every trusted comment of the item
The first plan request SHALL hold, under the key `comments`, every comment of the item that a person with write access or the Service App wrote, oldest first, each with its number, its author and its time: the comments of persons and the comments of the roadmap jobs. A comment of any other account SHALL NOT be in the request. The job SHALL collapse no comment.

#### Scenario: A decision of a person and a report of a job
- **WHEN** an item has a comment of the alternatives check and then a decision of a person
- **THEN** the first request holds both whole, oldest first, with `unlisted` 0, and the run offers `read_comment`

### Requirement: The comments of the first plan request fit its caps uncut
The comments SHALL take the room that the body leaves under its cap, and at most `CONST_ROADMAP_STAGE_COMMENTS_MAX_TOKENS` tokens of the context cap, at most half of it. The context SHALL lose only the tokens that the comments take past the room of the body. The newest comments SHALL come whole while they fit. Each older comment SHALL get an entry with `about`, its first line, in place of `text`, and `unlisted` SHALL count the older comments that no entry lists. No comment SHALL be cut.

#### Scenario: Comments at their caps
- **WHEN** a first request of code holds the context and the body at their caps and 41 comments, 40 of them long
- **THEN** the request stays under the limit of the tools with 512 tokens of headroom, the newest comment is whole, and the entries and `unlisted` count 41 comments

### Requirement: A staged item names the comments that its plan request held
The comment of a staged item SHALL name each comment that the plan request held whole, by its page. The key of the kept plan of an item SHALL hold its comments, so a new comment makes a new plan.

#### Scenario: The record of the comments
- **WHEN** a staged item has a comment whose page is known
- **THEN** the comment of the staged item names that page as a comment that the plan request held whole

# roadmap-refine Specification

## Purpose
The items that a round of `devops roadmap refine` looks at without `--item`, the order in which the round takes them, the one cap on their number, and the keys of the roadmap configuration that the roadmap jobs read.

## Requirements

### Requirement: Only the limit stops a refine round
Without `--item`, `devops roadmap refine` SHALL take up to `--limit` items in this order: each open milestone's New items, nearest milestone first, then the backlog's P0 and P1 New items, then the backlog's other New items, each place by priority. The number of Ready items in the open milestones and in the backlog SHALL NOT stop a round.

#### Scenario: A backlog full of Ready items
- **WHEN** the backlog holds twelve Ready items and New P3, P2, P1 and P3 items, an open milestone holds one New P3 item, and refine runs with `--limit 4`
- **THEN** refine asks the model about the milestone's item, the backlog's P1 item, the backlog's P2 item and the backlog's first P3 item, in that order, and about no other item

### Requirement: Refine records the paths that cause a block
When refine leaves an item New with an open dependency or a suspected block, it SHALL record in the job record, as `refine.block_paths`, the paths of the proposal's `block_paths` that the checkout holds at the refined commit: each path one time, without its line, at most five, and none outside the repository. It SHALL record no path for a proposal with no open dependency and no suspected block.

#### Scenario: A proposal cites paths that the checkout holds and paths that it does not hold
- **WHEN** the proposal of a New item has a suspected block, and its `block_paths` are `src/sample.py:1`, `src/missing.py`, `../CONTEXT.md`, `/etc/hosts`, `src/sample.py` and `CONTEXT.md`, and the checkout holds `src/sample.py` and `CONTEXT.md`
- **THEN** the job record holds `refine.block_paths` `src/sample.py,CONTEXT.md`

#### Scenario: A proposal with no block
- **WHEN** the proposal of a New item gives `block_paths` `src/sample.py` and has no suspected block and no dependency
- **THEN** the job record holds no `refine.block_paths`

### Requirement: The next-step comment names the cited files
The comment that gives an item its next step SHALL end with a line that names each recorded file, when refine records a path for the item, and SHALL name no file when it records none.

#### Scenario: A comment for an item whose block cites code
- **WHEN** refine records `refine.block_paths` `src/sample.py,CONTEXT.md` for an item
- **THEN** the last line of refine's comment on the item names `src/sample.py` and `CONTEXT.md` as the files whose change on the default branch makes the next round look at the item again

#### Scenario: A comment for an item with no block
- **WHEN** refine records no `refine.block_paths` for an item
- **THEN** refine's comment on the item names no cited file

### Requirement: A change to the code that a block cites ends the wait
Without `--item`, `devops roadmap refine` SHALL look at an unchanged waiting item again when a commit on the default branch changed one of its recorded `refine.block_paths` at or after refine's last comment on the item. When no recorded path changed after that comment, the item SHALL keep waiting on its next step, and the round SHALL make no model call for it.

#### Scenario: The cited path changes after refine's last comment
- **WHEN** an item waits on an open blocker, or on a suspected block, with `refine.block_paths` `src/sample.py`, and a commit on the default branch changes `src/sample.py` five minutes after refine's last comment on the item
- **THEN** the next round refines the item again, with one model call, and the item is not waiting

#### Scenario: The cited path does not change after refine's last comment
- **WHEN** an item waits on an open blocker with `refine.block_paths` `src/sample.py`, the newest commit that changed `src/sample.py` is one day before refine's last comment, and a later commit changes only `CONTEXT.md`
- **THEN** the next round leaves the item waiting on its blocker and makes no model call

#### Scenario: The dry-run plan of a round
- **WHEN** `devops roadmap refine --dry-run` plans a round without `--item`, and when it plans a round with `--item 7`
- **THEN** the round's plan lists one read of the newest commit that changed each cited path of a waiting item, under the condition that no comment follows refine's last comment, and the plan with `--item` lists no such read

### Requirement: Refine investigates a question that has no verified source
When a validated proposal has a fact or a decision with no verified source, or a body key question that no answer names, refine SHALL run one investigation for the item with read-only tools on the pinned commit, and with web search for a public repository with at least one configured search provider. Refine SHALL validate the proposal that the investigation returns as it validates the first. When nothing is open, refine SHALL make no investigation request.

#### Scenario: A fact that a file read settles
- **WHEN** the first proposal answers "Where is the sample function?" as a fact with no source, and the investigation reads `src/sample.py` and answers with the source `src/sample.py:1`
- **THEN** the item has no open question, and refine sets it to Ready

#### Scenario: A fact that a web search settles
- **WHEN** the repository is public, a search provider is configured, the investigation's web search returns `https://example.com/gitleaks`, and the investigation answers the fact with that URL as its source
- **THEN** the item has no open question, and refine sets it to Ready

#### Scenario: A proposal with nothing open
- **WHEN** the first proposal has no open question
- **THEN** refine makes one model request for the item and runs no investigation

### Requirement: A stopped investigation keeps the first proposal
When the investigation stops with no proposal, refine SHALL keep the first proposal. When a question that is not marked "(a person decides)" is still open, refine SHALL record a job failure with the failed check `investigation_stopped` and the first line of the error, and SHALL NOT keep that question as a wait on a person.

#### Scenario: The investigation stops with no proposal
- **WHEN** the investigation asks for more tool calls than its budget holds, and the first proposal holds only a `(proposed)` decision
- **THEN** refine keeps the first proposal, and the item is not a failed item

#### Scenario: The output retries run out
- **WHEN** the investigation of an item with a `(missing verified source)` question stops with `Exceeded maximum output retries (2)`
- **THEN** the item has the next step `retry`, its job record names the check `investigation_stopped` and holds the error, and no comment lists the question

### Requirement: A decision names its options and the practice it follows
A decision SHALL list the options it compared, each with the reason it was chosen or rejected, and the refined section SHALL show them. A decision whose answer quotes an owner decision of the body SHALL show "(owner decision)", one with a verified source SHALL show "(best practice)", and one with none SHALL show "(proposed)". An answer SHALL end with only the mark it earns. No decision SHALL make the item wait on a person.

#### Scenario: A sourced decision
- **WHEN** a decision chooses "Use the library" over "Write a parser", cites `src/sample.py`, and gives a reason for each option
- **THEN** the section shows the answer with "(best practice)", the chosen option and the rejected option with their reasons, and the item can be Ready

#### Scenario: A mark copied from an earlier section
- **WHEN** a decision with the verified source `src/sample.py` answers "Use the library. (proposed)"
- **THEN** its answer is "Use the library. (best practice)"

### Requirement: Only a person's decision waits on a person
A question of kind `person` SHALL be an open question with "(a person decides)", and the item SHALL wait on a person. An open question with no such mark SHALL NOT make an item wait on a person.

#### Scenario: A decision that AGENTS.md reserves for a person
- **WHEN** the proposal asks "Which repository secret holds the key?" as a `person` question and the proposal passes its form check
- **THEN** the item waits on a person, and the comment lists "Which repository secret holds the key? (a person decides)"

### Requirement: The body's answered key questions are not asked again
Refine SHALL read the body's "Key questions" section as CommonMark, up to the next heading of the same or a higher level. Only a top-level list item whose first paragraph holds a question mark SHALL be a question. Text after its last question mark, or a block inside the item after that paragraph, SHALL answer it. Refine SHALL send the other questions numbered, and a number that no answer names SHALL be an open question.

#### Scenario: A body that answers its own questions
- **WHEN** the body's "Key questions" hold "- *Which ADR number?* (proposed) The next free one.", "- *Which files?*" with an indented answer under it, and "- #1336 owns the directory."
- **THEN** refine sends no body question and reports no open question

#### Scenario: A body question that no answer names
- **WHEN** the body's "Key questions" hold "- *Which store holds the record?*" and no answer names number 1
- **THEN** "*Which store holds the record?*" is an open question

#### Scenario: A question that wraps, and a paragraph after the list
- **WHEN** the body's "Key questions" hold "- How should refine handle a body" with "that wraps across lines?" on the next line, then a blank line and the paragraph "Context: the Service writes it hourly."
- **THEN** "How should refine handle a body that wraps across lines?" is the one body question

### Requirement: A round leaves an item from an account without write access to a person
Without `--item`, `devops roadmap refine` SHALL take only an item whose author the jobs trust (`roadmap-author-trust`). Any other item SHALL wait on a person with a detail line that names its author, its association and `--item` with its number. It SHALL take no place under `--limit`, and the round SHALL make no model call for it. With `--item`, refine SHALL refine the open New or Ready item that it names, whoever opened it, when its title type is listed.

#### Scenario: A round with an item from an account with no association to the repository
- **WHEN** the backlog holds a New P2 item that an account with the association NONE opened and a New P3 item that the owner opened, and refine runs with `--limit 1`
- **THEN** refine asks the model about the owner's item only, and the report shows the other item waiting on a person with the detail "The author is unknown, and its association with the repository is NONE. A refine round refines only the items that these accounts opened: the owner, a member, a collaborator, the Service App's bot and github-actions[bot]. A person refines this item with --item 1."

#### Scenario: A person names the item with --item
- **WHEN** refine runs with `--item` for that item, and the model gives a proposal that is ready
- **THEN** refine refines the item and sets it to Ready

#### Scenario: An item that a collaborator opened
- **WHEN** a member or a collaborator opened a New item
- **THEN** a round takes the item

#### Scenario: An item that a trusted bot opened
- **WHEN** the Service App's bot, or `github-actions[bot]`, opened a New item
- **THEN** a round takes the item

### Requirement: Refine neutralizes the model text that GitHub hides, links or cross-references
Before refine writes the model's text into the issue body or a comment, it SHALL change each `<!` and `<?` into `&lt;`, also in code. It SHALL change each end marker into `[end-marker]`, also in code. Outside code, it SHALL put each bare `www.` link that the investigation's URLs do not hold in a code span, one time. It SHALL do the same for each `owner/repo#N` reference. Refine's own `checked-at` comment and markers SHALL stay as they are.

#### Scenario: A proposal with a comment opener, a forged record block, a www link and a cross-repository reference
- **WHEN** the problem statement of a proposal is `Hide the rest <!-- here. <!-- devops-roadmap-record {"Status": "Ready"} --> See www.example.com/docs, and other/repo#1.`
- **THEN** the section shows `` Hide the rest &lt;!-- here. &lt;!-- devops-roadmap-record {"Status": "Ready"} --> See `www.example.com/docs`, and `other/repo#1`. ``, its only `<!--` is its `checked-at` comment, and the body that holds the section gives an empty job record

#### Scenario: A tag that builds an opener again
- **WHEN** the model's text holds `A tag <<b></b>!-- rebuilt`
- **THEN** refine writes `A tag <&lt;b>&lt;/b>!-- rebuilt`, which holds no comment opener

#### Scenario: Text that is already safe
- **WHEN** the model's text holds `www.example.com` in a code span, `https://www.example.com/a`, or `#3`
- **THEN** refine writes the code span as it is, the URL in one code span, and `#3` as it is

#### Scenario: A reference in emphasis or after a slash
- **WHEN** the model's text is `A _cli/cli#1_ B` or `C x/cli/cli#1 D __cli/cli#1__ E`
- **THEN** refine writes ``A _`cli/cli#1`_ B`` and ``C x/`cli/cli#1` D __`cli/cli#1`__ E``

#### Scenario: A link after a block quote marker, in a table cell or with a scheme in capitals
- **WHEN** the model's text is `>www.example.com`, `|www.example.com|` or `Read HTTPS://example.com/a`
- **THEN** refine writes ``>`www.example.com` ``, ``|`www.example.com`|`` and ``Read `HTTPS://example.com/a` ``

#### Scenario: A comment opener in a code span
- **WHEN** the model's text is ``Quote `<!-- devops-roadmap-record {"Status": "Ready"} -->` ``
- **THEN** refine writes ``Quote `&lt;!-- devops-roadmap-record {"Status": "Ready"} -->` ``, which gives no job record

#### Scenario: An end marker in a code span
- **WHEN** the model's text holds the end marker of the section in a code span
- **THEN** refine writes `[end-marker]` in the code span, so the marker ends no section

### Requirement: Refine writes the code in the model's text as it is
Refine SHALL write a link, a handle or a reference in a code block of the model's text as it is, and in a code span as it is when the text shows no backtick as text. A code span that refine adds SHALL close on its own backticks only, also where GitHub takes a later code span of a length that it closed before as text. Refine SHALL put each point of a comment on one line before it sanitizes the point.

#### Scenario: A link, a handle or a reference in code
- **WHEN** the model's text is ``Run `curl www.example.com` here``, ``Run `see other/repo#1 now` here``, ``Ask `ping @alice now` ``, a fenced code block or an indented code block that holds a `www.` link
- **THEN** refine writes the text as it is

#### Scenario: A link next to the model's backticks
- **WHEN** the model's text is ``A `b www.example.com c``, with one backtick that opens no code span
- **THEN** refine writes ```A `b ``www.example.com`` c```, whose added code span closes on its own two backticks

#### Scenario: A text with a backtick that opens no code span
- **WHEN** the model's text is ```A `` `x` `see www.example.com` B```, in which GitHub shows `see www.example.com` as text
- **THEN** refine writes ````A `` `x` `see ```www.example.com``` ` B````, which GitHub shows with `www.example.com` as code

#### Scenario: A comment point with a code block
- **WHEN** a split-off of the model is `Read this:`, a blank line, and `www.example.com` indented by four spaces
- **THEN** the comment shows the point as ``1. Read this: `www.example.com` ``

### Requirement: Refine writes at most two comments on one item in a day
Without `--item`, a refine round SHALL leave an item alone, with no model call and no comment, when refine wrote `CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM` (2) comments that carry its marker on the item in the last 24 hours. The item SHALL wait on a person with the reason in the plan, and SHALL take no place under the round's limit. Comments older than 24 hours SHALL NOT count.

#### Scenario: Two refine comments within the day
- **WHEN** refine wrote two comments on an item 23 hours ago, another bot replied to each, and a round runs with `--confirm`
- **THEN** the round makes no model call and writes no comment, the item waits on a person with the reason, and one warning and one count name the cap

#### Scenario: Two refine comments older than the day
- **WHEN** the two comments and the replies are 25 hours old
- **THEN** the round refines the item and writes its comment

#### Scenario: Items at the cap fill no place
- **WHEN** another bot replied to two refine comments on each of three P0 items in the last hour, a P1 item is New, and a round runs with a limit of 3
- **THEN** the round refines the P1 item with one model call, and the three P0 items wait on a person

### Requirement: Each comment that the cap stops counts once
The cap stops the comment that would answer the item's newest comment. For each such comment that no earlier round recorded, `--confirm` SHALL record the comment's creation time in the item's job record as `refine.capped_after`, log one warning and add 1 to `devops_cli_roadmap_refine_comments_capped_total`. A round that finds the recorded comment still the newest SHALL write, log and count nothing for the item.

#### Scenario: A round with no newer comment counts nothing
- **WHEN** a round stopped the comment on an item at the cap, a second round runs, a person then replies, and a third round runs
- **THEN** the second round writes nothing, and the third round counts and logs one more stopped comment and records the reply's time

### Requirement: A person refines an item at the cap
`devops roadmap refine --item` SHALL refine the item it names at the cap on refine's comments, since a person asked for it, and SHALL count no stopped comment.

#### Scenario: A person refines an item at the cap
- **WHEN** a person runs `devops roadmap refine --item <number> --confirm` on an item at the cap
- **THEN** refine refines the item and posts its comment, and counts no stopped comment

### Requirement: Refine writes each acceptance criterion as an OpenSpec requirement
The refine reply SHALL give each acceptance criterion as `name`, `requirement`, `scenario`, `when` and `then`, and the proposed design SHALL render it as an OpenSpec requirement block: `### Requirement: <name>`, the requirement text, `#### Scenario: <scenario>`, and the `- **WHEN**` and `- **THEN**` lines.

#### Scenario: A criterion in the proposed design
- **WHEN** refine renders a proposal whose criterion has the name `Token cost`, the requirement `The tuner SHALL read the token cost from the ledger.`, the scenario `The ledger has the backend`, the WHEN `the ledger holds records for the backend` and the THEN `the tuner sends no probe`
- **THEN** the section holds `### Requirement: Token cost`, the requirement line, `#### Scenario: The ledger has the backend`, `- **WHEN** the ledger holds records for the backend` and `- **THEN** the tuner sends no probe`, and no `Criterion` or `Verification:` line

#### Scenario: A criterion with the old keys
- **WHEN** a reply gives a criterion as `description` and `verification`
- **THEN** the reply fails validation

### Requirement: A criterion's requirement says SHALL or MUST
The refine reply SHALL be refused when the `requirement` of a criterion does not contain the word SHALL or MUST, as OpenSpec requires of a requirement's text.

#### Scenario: A requirement without the keyword
- **WHEN** a reply's criterion has the requirement `The tuner reads the ledger.`
- **THEN** the reply fails validation with an error that names SHALL and MUST

### Requirement: Refine answers the existing-tool question
The refine reply SHALL carry `existing_tool`: the open, maintained tool or library that covers the need and what it lacks, or the written cost of building instead. Refine SHALL set an item Ready only when that answer is not empty, and SHALL render it under `### Existing Tool Considered`.

#### Scenario: The answer in the proposed design
- **WHEN** refine renders a proposal whose `existing_tool` is `Renovate covers the pin.`
- **THEN** the section holds a `### Existing Tool Considered` heading followed by that text

#### Scenario: An empty answer
- **WHEN** a proposal meets every other readiness rule and its `existing_tool` is empty
- **THEN** refine does not set the item Ready

#### Scenario: A reply without the key
- **WHEN** a reply has no `existing_tool` key
- **THEN** the reply fails validation

### Requirement: The request holds the recorded check for alternatives
The proposal request and the investigation request of an item SHALL hold the key `alternatives`. For an item whose body holds the alternatives job's block and whose job record holds a verdict, it SHALL be an object with the verdict, the tool URL or null, the block, and the job's latest comment cut to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS`. Otherwise it SHALL be null. The comment of the job SHALL NOT be one of the `replies`.

#### Scenario: A partly check
- **WHEN** refine plans an item whose job record holds the verdict `partly` and a tool, with the block in its body
- **THEN** the proposal request holds `alternatives` with that verdict, that tool and the text of the job's comment, and the `replies` hold no comment of the job

#### Scenario: No check
- **WHEN** refine plans an item with no block in its body
- **THEN** the request holds `alternatives` null

#### Scenario: A block that a person deleted
- **WHEN** the job record holds a verdict and the body holds no block
- **THEN** the request holds `alternatives` null

### Requirement: A covers verdict is a question that only a person answers
When the recorded check of an item has the verdict `covers`, refine SHALL add the question to adopt the tool or to keep the item with a reason. While no comment of a person follows the job's latest comment, the question SHALL be open with the mark of a question for a person. A comment of a roadmap job is no comment of a person. An item with an open question has the next step `PERSON`, and the Ready check SHALL NOT set it Ready. A `partly` or `none` check SHALL add no question.

#### Scenario: No reply yet
- **WHEN** refine plans a New item with a `covers` check and no comment of a person after the job's comment, and the model answers every other question
- **THEN** the item's next step is `PERSON`, the step comment lists the adopt-or-keep question naming the tool, and the item is not Ready

#### Scenario: Not answered by the model
- **WHEN** no person replied and the model gives a `decision` answer that names the question's number
- **THEN** the question is still open

#### Scenario: A reply and an answer
- **WHEN** a person replied after the job's comment and the proposal answers the question with a `decision`
- **THEN** the question is closed and refine sets the item Ready when every other rule holds

#### Scenario: A reply and no answer
- **WHEN** a person replied after the job's comment and no answer names the question
- **THEN** the question is open and the next step is `PERSON`

#### Scenario: A partly check
- **WHEN** refine plans an item with a `partly` check that otherwise meets every rule of the Ready check
- **THEN** refine sets the item Ready

### Requirement: A reply to a covers question is answered by the proposal
After a comment of a person follows the job's latest comment, the `covers` question SHALL join the numbered key questions of the request. It SHALL be open until an answer names its number, and an answer of kind `person` SHALL leave it open.

#### Scenario: The job left no comment
- **WHEN** the item holds a `covers` record and block, no comment of the job, and a person replied
- **THEN** the question is answered, and a `decision` answer that names it closes the question

#### Scenario: A comment of another job
- **WHEN** only a comment of the stage job or of intake follows the job's comment
- **THEN** the question is not answered

#### Scenario: A person answer
- **WHEN** a person replied after the job's comment and the model gives an answer of kind `person` that names the question
- **THEN** the question is open and the next step is `PERSON`

### Requirement: The request carries the replies that answer a covers question
The `alternatives` key SHALL hold `answers`: for a `covers` check, the replies of persons since the check (the newest `CONST_ROADMAP_REFINE_MAX_REPLIES`, each cut to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS`), and for any other check an empty list.

#### Scenario: Refine commented after the reply
- **WHEN** a person answered the `covers` question, refine commented again, and a person made a later comment
- **THEN** the request holds the first reply in `alternatives.answers` and only the later comment in `replies`, and a `decision` answer closes the question

### Requirement: A new covering tool brings an item back to refine
Refine SHALL record the URL of the covering tool it asked about as `refine.alternatives_asked`, and SHALL clear the key when the recorded check does not cover. An open New or Ready item whose job record holds a `covers` verdict with a tool URL that differs from the key SHALL be selected in the next round, though its body is unchanged, and without a read of its comments. A Ready item so selected SHALL go back to New when the question stays open.

#### Scenario: A Ready item gets a covers check
- **WHEN** a Ready item that refine refined earlier gets a `covers` check
- **THEN** the next round selects it, and writes the question, the next step `PERSON` and Status New

#### Scenario: The same tool is found again
- **WHEN** a re-check finds the same covering tool and refine asked about it
- **THEN** a Ready item is not selected and a waiting item keeps its wait

#### Scenario: A waiting item and a new tool
- **WHEN** a New item waits on a person, no person replied, and a re-check records another covering tool
- **THEN** the next round refines the item

### Requirement: The hash of the body leaves out the job's block
The hash that refine records as `refine.body_hash` SHALL be the hash of the body outside the alternatives job's block and refine's section, as the check for an unchanged item computes it. The check before a write SHALL compare the hash of the whole body outside refine's section, so a block that the job wrote after refine read the body is kept.

#### Scenario: An item with a block reads as unchanged
- **WHEN** refine refines an item whose body holds the job's block, and the next round reads the item with no change
- **THEN** the item reads as unchanged and the round does not refine it

#### Scenario: The job writes a block during the round
- **WHEN** the job writes a block between the read and the write of refine
- **THEN** refine does not write the body, and the block stays

### Requirement: The warning of a failed model call names the repository and the cause
Refine SHALL write one warning for an item whose model call failed. It SHALL name the repository and the item number, the class of the error, and the `reason` of the `AIClientError`: its error code with its HTTP status or `timeout`. The error that ends the round, the job record and the comments on the issue SHALL keep their text.

#### Scenario: A failed call names the repository and the status
- **WHEN** the model call for #42 of the repository `example/one` fails with an `AIClientError` whose status is 408
- **THEN** the warning holds `#42 in example/one`, `LLM_INFERENCE_ERROR` and `HTTP 408 Request Timeout`

#### Scenario: A failed call that timed out
- **WHEN** the model call fails with an `AIClientError` that timed out
- **THEN** the warning holds `LLM_INFERENCE_ERROR` and `timeout`

#### Scenario: A warning names a timeout
- **WHEN** the model call fails with an `AIClientError` whose status is 408
- **THEN** the warning holds `timeout`

#### Scenario: A failed call with no status
- **WHEN** the model call fails with an `AIClientError` that has no status and did not time out
- **THEN** the warning holds `LLM_INFERENCE_ERROR` and no status

#### Scenario: A failed item keeps its error text
- **WHEN** the model call fails for an item and the round ends
- **THEN** the error of the round names the item with the class of the error and the count of schema violations, as before

### Requirement: The warning of a stopped investigation names the repository and the message
Refine SHALL write one warning for an item whose investigation stopped with no proposal. It SHALL name the repository and the item number, the class of the pydantic-ai error, and the fixed description in the first line of its `message`, masked and cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters. It SHALL NOT hold the `body` of the error, a later line of the message, data of the model's reply, or a control character.

#### Scenario: A stopped investigation gives the message
- **WHEN** the investigation of #1 in `example/two` stops with `UnexpectedModelBehavior` whose message is `Exceeded maximum output retries (3)`
- **THEN** the warning holds `#1 in example/two`, `UnexpectedModelBehavior` and `Exceeded maximum output retries (3)`

#### Scenario: The body of the error stays out
- **WHEN** the investigation stops with `UnexpectedModelBehavior` whose body is `MODEL-TEXT`, and whose message has the second line `input_value=MODEL-TEXT`
- **THEN** the warning holds the first line of the message, and neither the body nor the second line

#### Scenario: A secret in the message
- **WHEN** the first line of the message holds a token in the form of a GitHub token
- **THEN** the warning holds the mask in place of the token

#### Scenario: Data of the reply in the message
The fixed description is the text before a quoted part, a `:`, a `;` or a `=`, because pydantic-ai writes data of the reply after those marks.
- **WHEN** the investigation stops with `UnexpectedModelBehavior` whose message is ``Function tool calls must have unique `tool_call_id` values; duplicate `tool_call_id`s: ['MODEL-ID']``
- **THEN** the warning holds `Function tool calls must have unique <text> values` and no `MODEL-ID`

#### Scenario: A control character in the message
- **WHEN** the first line of the message holds an escape or a null character
- **THEN** the warning holds neither

### Requirement: The refine reply can defer a part of the item
The refine reply SHALL accept the key `deferred`: a list of at most 3 parts, each with a non-empty `title` and a non-empty `body`. The key SHALL default to an empty list. The reply SHALL be refused when a part has another key, when a part has an empty `title` or `body`, or when the list holds more than 3 parts.

#### Scenario: A reply with two parts
- **WHEN** a reply gives `deferred` with two parts, each with a title and a body
- **THEN** the proposal holds both parts in order

#### Scenario: A reply with four parts
- **WHEN** a reply gives `deferred` with four parts
- **THEN** the reply fails validation

#### Scenario: A reply without the key
- **WHEN** a reply gives no `deferred`
- **THEN** the proposal holds no part, and the round behaves as it did before

### Requirement: A deferred part does not block Ready
Refine SHALL decide `is_ready` on the proposal without its deferred parts. `fits_one_pr`, `split_offs` and `NextStep.SPLIT` SHALL keep their meaning for an item that is too big for one pull request.

#### Scenario: A complete proposal with a deferred part
- **WHEN** the proposal has a problem statement, a complete criterion, an existing-tool answer, no open question, no block, `fits_one_pr` true and one deferred part
- **THEN** the planned item is Ready and its next step is `ready`

#### Scenario: A proposal that is too big
- **WHEN** the proposal has `fits_one_pr` false and two `split_offs`
- **THEN** the next step is `split` and the item is not Ready

### Requirement: Refine files each deferred part through intake when it sets the item Ready
When refine plans an item Ready with deferred parts, it SHALL make one intake plan for each part, with a candidate that has no `source`, and `--confirm` SHALL file the parts through intake before refine writes the section or the status. The body of each new issue SHALL start with `Split from #<issue>.`. Refine SHALL file no part for an item that is not Ready. Refine SHALL set the Status of a new issue and its Priority through intake only, and SHALL set no milestone.

#### Scenario: Two parts on a Ready item
- **WHEN** a round with `--confirm` refines a New item whose proposal is complete and holds two deferred parts, and intake places both
- **THEN** two issues exist with the part titles, their bodies start with `Split from #<issue>.`, and the item is Ready

#### Scenario: An item that stays New
- **WHEN** the proposal holds an open question and one deferred part
- **THEN** refine files no issue, and the item stays New with the next step `person`

#### Scenario: A plan without `--confirm`
- **WHEN** a round plans an item with a deferred part and does not confirm
- **THEN** the plan holds the intake plan of the part and the store holds no new issue

### Requirement: A deferred part is linked by a body line, a comment and a record
Refine SHALL NOT link a deferred part as a sub-issue of the item. After it files the parts, refine SHALL add one sentence that names each new issue number to the Ready comment of the item, SHALL NOT post another comment, and SHALL record the numbers, comma separated, as `refine.deferred` in the job record.

#### Scenario: The links of two parts
- **WHEN** refine files two parts of item 7 as issues 21 and 22
- **THEN** the Ready comment of item 7 names `#21` and `#22`, the job record of item 7 holds `refine.deferred` `21,22`, and item 7 has no sub-issue

### Requirement: A part that intake cannot place keeps the item New
When the intake plan of a deferred part has no placement, or the text of the part is refused as a secret, refine SHALL NOT set the item Ready, SHALL file no part of the item, and SHALL give the item the next step `person` with a detail that names the part.

#### Scenario: Intake skips a part
- **WHEN** a complete proposal holds a deferred part and the intake model gives no usable proposal for it
- **THEN** the item stays New, the next step is `person`, its detail names the part title, and no issue is filed

### Requirement: A deferred part is filed once
The request to the proposal model SHALL carry `deferred_issues`: the number and title of each issue in the `refine.deferred` record of the item. Refine SHALL drop a deferred part whose title equals, with the white space joined, the title of a recorded issue. When a round files only some parts, refine SHALL record their numbers, SHALL write no section and no status, and SHALL log a warning that names the item.

#### Scenario: A part filed in an earlier round
- **WHEN** the job record holds `refine.deferred` `21` for an item, issue 21 has the title `Decide the storage` and the model defers a part with that title again
- **THEN** the intake plan holds no candidate for it and the request held `deferred_issues` with issue 21

#### Scenario: A write fails for the second part
- **WHEN** the store refuses the creation of the second of two parts
- **THEN** the job record holds the number of the first issue as `refine.deferred`, the body and Status of the item are as they were, and a warning names the item

### Requirement: The dry run lists the requests of a deferred part
`devops roadmap refine --dry-run` SHALL list the requests of one intake candidate, with the condition that the proposal defers a part, in the plan of a round and in the plan of `--item`. It SHALL make no request.

#### Scenario: The plan of an item
- **WHEN** the plan of `devops roadmap refine --item 7 --dry-run` is built
- **THEN** its requests hold the creation of an issue with the condition "the proposal defers a part of the item", and no request was sent

### Requirement: The context lists the tests and the callers of a cited symbol
The context that the stage and refine jobs give the model SHALL hold, for up to five identifiers that the item cites in backticks, the source files of the checked-out commit that name each one as a whole word, Markdown files excepted. It SHALL name the file and line of up to three definitions, then the test files, then the callers. A test file is under `tests/` or named `test_*.py` or `*_test.py`; every other file is a caller. An identifier that no file names SHALL add no section.

#### Scenario: A cited symbol is named by tests and by source files
- **WHEN** an item cites `hello_world`, and `tests/test_sample.py`, `pkg/test_inline.py` and `pkg/inline_test.py` name it, and `src/caller.py`, `src/contest.py` and `src/sample.py` name it
- **THEN** the context holds the section "Tests and callers of `hello_world`", the three test files under "Tests:" and the three source files under "Callers:"

#### Scenario: A cited Rust function
- **WHEN** an item cites `explorer_patrol_system`, which `src/game/unit.rs` defines on line 5 and calls, and `tests/patrol.rs` calls it
- **THEN** the section of `explorer_patrol_system` holds "Defined at: src/game/unit.rs:5", `tests/patrol.rs` under "Tests:" and `src/game/unit.rs` under "Callers:"

#### Scenario: A cited symbol that no file names
- **WHEN** an item cites `missing_symbol` and no source file names it
- **THEN** the context holds no section "Tests and callers"

### Requirement: The paths of one symbol are bounded
The context SHALL list at most `CONST_ROADMAP_REFINE_MAX_PATHS_PER_SYMBOL` paths for one cited identifier, 50 paths, and SHALL list the tests before the callers when the list is cut. When it cuts the list, the context SHALL say how many paths it shows, how many files name the identifier, and how many it leaves out.

#### Scenario: More files name a symbol than the bound
- **WHEN** the bound is 3, and five test files and one source file name the cited identifier `hello_world`
- **THEN** the section of `hello_world` lists three test files and no caller, and ends with the line "(3 of 6 paths shown; 3 more left out)"

### Requirement: The context names the requirements of the specs that cover a cited file
The context SHALL hold the names of the `### Requirement:` headings of each base spec in `openspec/specs/` that covers a cited file, in the order of the spec, for up to five specs and up to 40 names each. A spec covers a module of `src/devops_cli` when its name is the package and the module joined with hyphens, or the start of that name up to a hyphen. A spec also covers a file when its text names the path of the file. A spec that covers no cited file SHALL add no section.

#### Scenario: A cited module has a spec of its name
- **WHEN** an item cites `src/devops_cli/widget/render.py`, and `openspec/specs/widget-render/spec.md` holds two requirements, and `openspec/specs/widget/spec.md` holds one, and `openspec/specs/other/spec.md` holds one
- **THEN** the context holds the section "Requirements of widget-render" with both names, and the section "Requirements of widget" with its name, and no name from `other`

#### Scenario: A spec names the path of a cited file
- **WHEN** an item cites `src/devops_cli/widget/render.py`, and the text of `openspec/specs/named-by-path/spec.md` names that path
- **THEN** the context holds the section "Requirements of named-by-path" with the requirement names of that spec

#### Scenario: No spec covers the cited file
- **WHEN** an item cites `src/sample.py` and no spec covers it
- **THEN** the context holds no section "Requirements of"

### Requirement: The new sections come before the cited code and stay inside the budget
The context SHALL put the sections of tests and callers and of requirement names before the cited code, so the cut of the token budget, which takes the end first, keeps them. The whole context SHALL stay inside the token budget that the job gives it.

#### Scenario: The sections come before the code
- **WHEN** an item cites `src/devops_cli/widget/render.py` and the spec `widget-render` covers it
- **THEN** the section "Requirements of widget-render" is before the section "Code: src/devops_cli/widget/render.py"

#### Scenario: A small budget
- **WHEN** forty test files name a cited identifier and the budget is 120 tokens
- **THEN** the context holds at most 120 tokens

### Requirement: The investigation reads the context window of the analysis task
The investigation of an item SHALL pass the context window of the `analysis` task to the run, so that the run offers no tool to a request when its messages and a quarter of the window reach the window. The window SHALL end the tools of a run before the counts of requests and tool calls do when the window is small. The run SHALL keep both counts as the loop guard of the job.

#### Scenario: A small window
- **WHEN** the window of the `analysis` task is 6000 tokens and the model calls a tool in every reply
- **THEN** a request offers no tool before the count of requests, and the reply of the model ends the run with its proposal

#### Scenario: A large window
- **WHEN** the window is larger than any run can fill and the model calls a tool in every reply
- **THEN** the count of requests ends the tools, and the last request offers no tool

### Requirement: The refine reply holds no placeholder text
`RefinementProposal` SHALL use `ReplyText` for `problem_statement`, `existing_tool` and each free-text field of its acceptance criteria, key questions, options and deferred parts, and for each line of `split_offs`. `suspected_block` SHALL stay a plain text, because `none` is a valid value of it.

#### Scenario: x in both required keys
- **WHEN** a reply sets `problem_statement` and `existing_tool` to `x` and gives no acceptance criterion
- **THEN** the schema refuses the reply with two violations of the type `placeholder_text`

#### Scenario: A refusal of the task
- **WHEN** a reply sets `existing_tool` to "Not yet: I need to inspect the repository first."
- **THEN** the schema refuses the reply

#### Scenario: A real answer
- **WHEN** a reply sets `problem_statement` to a sentence and `existing_tool` to "Pydantic covers the schema check."
- **THEN** the schema accepts the reply

#### Scenario: No block
- **WHEN** a reply sets `suspected_block` to `none`
- **THEN** the schema accepts the reply

### Requirement: A placeholder reply is retried once and then fails
Refine SHALL ask the model for the proposal with one retry. A reply that holds a placeholder SHALL go back to the model with the schema report once. A second reply with a placeholder SHALL be a placeholder failure of the item: refine SHALL write the warning of a failed call, SHALL write no mark, no comment and no body for the item, SHALL ask no person and SHALL set no Status. The failure SHALL stay in `failed_items` of the plan.

#### Scenario: The retry answers well
- **WHEN** the first reply holds `x` as the problem statement and the second reply is valid
- **THEN** refine uses the second reply, and the model got two calls

#### Scenario: Two placeholder replies
- **WHEN** both replies hold `x` as the problem statement
- **THEN** the item gets no comment, no body change, no mark and no Status change, and `failed_items` names it

#### Scenario: A placeholder with another violation
- **WHEN** the last reply holds `x` as the problem statement and breaks another rule of the schema
- **THEN** the failure is a normal schema failure of the item

### Requirement: A placeholder failure does not fail the round
`raise_for_failed_items` SHALL NOT count a placeholder failure. A round whose only failures are placeholder failures SHALL succeed, so `FailureLedger` counts no failed round and does not suspend the refine row.

#### Scenario: Only a placeholder failure
- **WHEN** one item of a round fails with a placeholder failure and the others are refined
- **THEN** the round raises no error, and a ledger that ran it three times in a row does not suspend the row

#### Scenario: A placeholder failure and another failure
- **WHEN** one item fails with a placeholder failure and another fails with a timeout
- **THEN** the round raises an error that names the timeout item only

### Requirement: An item the stage job returned gets one new look
Without `--item`, `devops roadmap refine` SHALL refine again an unchanged New item whose `refine.next_step` is `ready` when a comment of the stage job follows refine's last comment and the item holds no `stage.branch`, with no reply of a person and no body edit. An item that a person set back to New with no such comment SHALL keep waiting on a person, with the reason that a reply makes refine look again.

#### Scenario: A stage return follows refine's last comment
- **WHEN** refine set an item Ready, the stage job commented with its marker and set the item to New, and no person replied
- **THEN** the next round refines the item again, with one model call, and the item is not waiting

#### Scenario: A person sets the item back
- **WHEN** refine set an item Ready, a person set it to New with no comment, and the stage job wrote nothing after refine's last comment
- **THEN** the next round leaves the item waiting on a person with the reason that a reply makes refine look again, and makes no model call

### Requirement: The model reads the evidence of a stage return
The request of a proposal call SHALL hold the key `stage_return`: the text of the newest comment of the stage job after refine's last comment on an item with no `stage.branch`, without the marker and cut to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS`, or `null` when there is none. The comments of the stage job SHALL stay out of `replies`.

#### Scenario: The request after a return
- **WHEN** the stage job returned an item with the evidence "It returns a fixed text." and refine looks at the item again
- **THEN** `stage_return` holds "It returns a fixed text.", holds no marker, and `replies` is empty

#### Scenario: The request of an item with no return
- **WHEN** refine refines an item that the stage job never returned
- **THEN** `stage_return` is `null`

### Requirement: A second stage return on the same body waits on a person
A round that refines an unchanged item after a stage return SHALL record its body hash in `refine.returned_body_hash`. Any other round SHALL clear the key. An item whose `refine.returned_body_hash` equals its `refine.body_hash` and that the stage job returned again SHALL wait on a person, with the reason that the job returned it twice on the same body, and with no model call. A reply or a body edit SHALL end that wait.

#### Scenario: The second return
- **WHEN** refine set an item Ready, the stage job returned it, refine looked again and set it Ready, and the stage job returned it again
- **THEN** the item waits on a person with the reason "The stage job returned the item to New twice on the same body. A reply or a body edit makes refine look at it again." and the round makes no model call

#### Scenario: A body edit between two returns
- **WHEN** a person edits the body of an item after its first return
- **THEN** the next round refines the item and clears `refine.returned_body_hash`

### Requirement: A wait on a person ends when a cause that its text names ends
Without `--item`, `devops roadmap refine` SHALL look at an unchanged item that waits on a person again when an issue that the last refine comment on the item names closed at or after that comment, or a file that the comment names changed on the default branch at or after that comment. The named files SHALL NOT need to be in `refine.block_paths`. An issue that closed before the comment, an issue of another repository, and the number of the item itself SHALL end no wait.

#### Scenario: A named issue closes after the comment
- **WHEN** an item waits on a person, the last refine comment on it asks about #12, and #12 closes after the comment
- **THEN** the next round refines the item again

#### Scenario: A named issue closed before the comment
- **WHEN** the last refine comment names #12 and #12 closed before the comment
- **THEN** the item keeps waiting and the round makes no model call

#### Scenario: A named file changes with no recorded block path
- **WHEN** an item waits on a person with no `refine.block_paths`, its last refine comment names `src/sample.py`, and a commit on the default branch changes that file after the comment
- **THEN** the next round refines the item again

### Requirement: A round bounds the new looks and the reads of a wait text
A round SHALL select no more items than its limit, new looks included. It SHALL read at most `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` issues and at most as many files from the text of one wait. The dry-run plan of a round without `--item` SHALL list these reads with their bound.

#### Scenario: More returned items than the limit
- **WHEN** four items were returned by the stage job and the limit of the round is 2
- **THEN** the round refines two items and makes two model calls

#### Scenario: A text that names many issues and files
- **WHEN** a wait text names 12 open issues and 12 files
- **THEN** the round reads 5 issues and 5 files for the item

### Requirement: Refine reviews a Ready proposal for an item of a bot
When the proposal for an item whose author is the Service App's bot or `github-actions[bot]` is ready, refine SHALL send the issue and the proposal to the verification pass of the stage job, with the model of the task slot `ai.tasks.verification`, before it plans the deferred parts. With no open finding, refine SHALL set the item Ready and record `refine.judge` `approved`. Refine SHALL make no review call for an item of a person.

#### Scenario: The review approves
- **WHEN** the proposal for a New item of the Service App is ready, and the review finds no open defect
- **THEN** the item is Ready, its job record holds `refine.judge` `approved`, and the review made one call

#### Scenario: An item of the owner
- **WHEN** the proposal for a New item of the owner is ready
- **THEN** refine makes no review call, sets the item Ready and records no `refine.judge`

### Requirement: A refusal keeps the item New and lists each finding
A finding of the type `missing_path`, `false_premise`, `ignores_existing_code` or `spec_delta_wrong`, or a placeholder, with a quote that the input holds, SHALL be an open finding. With an open finding, refine SHALL keep the item New, record `refine.judge` `refused` and the next step `edit`, and write one comment that lists each open finding with its evidence. A finding that is not open SHALL be advice, and the comment SHALL NOT list it.

#### Scenario: The review refuses
- **WHEN** the review finds a `false_premise` that quotes the problem statement, and a `contrived_test` with no quote
- **THEN** the item stays New, its job record holds `refine.judge` `refused` and `refine.next_step` `edit`, and refine's one comment lists the `false_premise` with its evidence and does not list the `contrived_test`

#### Scenario: A quote that the input does not hold
- **WHEN** the review finds a `false_premise` whose quote is in no text of the input
- **THEN** the item is Ready and its job record holds `refine.judge` `approved`

#### Scenario: A finding about tasks
- **WHEN** the review finds a `task_order` or a `verify_form` finding that quotes the input
- **THEN** the finding is advice, because a proposal holds no task group, and the item is Ready with `refine.judge` `approved`

### Requirement: The review looks again only after the body changes
Refine SHALL make no review call for an item that waits on its body edit, and for an item that holds `refine.judge` `approved` with an unchanged body. A body edit SHALL end the wait, and the next round SHALL review the new proposal.

#### Scenario: A second round on the same body
- **WHEN** a round follows the refusal and no one changed the body
- **THEN** the round leaves the item waiting on its body edit, makes no proposal call and no review call, and writes no second comment

#### Scenario: A body edit
- **WHEN** a person edits the body after the refusal, and the review finds no open defect
- **THEN** the next round makes one review call and sets the item Ready

#### Scenario: An approved item that a round looks at again
- **WHEN** a round looks again at an item that holds `refine.judge` `approved`, and its body is unchanged
- **THEN** refine keeps the approval and makes no review call

### Requirement: A round reviews a Ready item of a bot again when its approval ends
A round SHALL take a Ready item of a trusted bot when its approval does not hold. The approval does not hold when `refine.judge` is not `approved`, or when the body hashes differently from `refine.body_hash` and `refine.section_hash`. The round SHALL review the new proposal. With no open finding, the item SHALL stay Ready with a new approval. With an open finding, the item SHALL go back to New.

#### Scenario: A person edits the body of an approved item
- **WHEN** refine approved a Ready item of the Service App, and a person adds a line to the body outside the section of refine
- **THEN** the item has no approval that holds, the next round makes one proposal call and one review call, and the item stays Ready with a new approval

#### Scenario: The review refuses the edited body
- **WHEN** the review finds an open defect in the proposal for the edited body
- **THEN** the item goes back to New, its job record holds `refine.judge` `refused` and `refine.next_step` `edit`, and no job takes it

#### Scenario: An approval that holds
- **WHEN** a Ready item of the Service App holds `refine.judge` `approved` and its body is unchanged
- **THEN** a round does not take the item for this reason

### Requirement: Refine tells the author of an item that the jobs do not trust one time
A round that leaves out an item that the jobs do not trust, and finds no comment that holds `CONST_ROADMAP_REFINE_OUTSIDE_MARKER` on it, SHALL write one comment that names the author, the association and `devops roadmap refine --item <number>`. A round that finds the marker SHALL write no comment. The comment SHALL not count as a reply to the model.

#### Scenario: Another bot opens an item
- **WHEN** `dependabot[bot]` opened a New item and two rounds run
- **THEN** the first round writes one comment that holds the marker and "Its author is dependabot[bot], and its association with the repository is CONTRIBUTOR.", the second round writes none, and neither round calls a model for the item

#### Scenario: An outside account opens an item
- **WHEN** an account with the association NONE opened a New item and two rounds run
- **THEN** the item has one comment that holds the marker after the second round

### Requirement: An open dependency that the proposal names blocks the item
`devops roadmap refine` SHALL give an item the next step `blocked` when its validated proposal names an open issue as a dependency. This applies when the proposal has no open question and fits one pull request. It SHALL record the open issues in `refine.blocked_by` and SHALL NOT set the Status to Ready. A Ready item SHALL go back to New. A closed dependency SHALL NOT hold the item back.

#### Scenario: A complete proposal with one open dependency
- **WHEN** a New item has a complete proposal with one open dependency (no open question, no split, no suspected block)
- **THEN** the next step is `blocked` with that issue, `refine.blocked_by` holds its number, and the item stays New

#### Scenario: A Ready item with an open dependency
- **WHEN** the proposal of a Ready item meets the same conditions, and a person runs refine for the item with `--item`
- **THEN** the item goes back to New, with the next step `blocked` and `refine.blocked_by` set

#### Scenario: A closed dependency
- **WHEN** a New item has a complete proposal with one closed dependency (no open question, no split, no suspected block)
- **THEN** the next step is `ready`, `refine.blocked_by` is empty, and the item is Ready

### Requirement: The last blocker to close ends the block
A blocked item SHALL wait while one of its recorded blockers is open, with no model call. The round after the last blocker closes SHALL refine the item again.

#### Scenario: The last blocker closes
- **WHEN** an item waits on two open dependencies, one of them closes, and then the other closes
- **THEN** the round after the first close leaves the item waiting on the second, with no model call. The round after the second close refines the item with one model call and sets it Ready

### Requirement: The review of refine runs with no tool
The review of an item SHALL run with a plain client that has no tool, and its prompt SHALL name no tool and no repair round, because only an agent run of the stage job reads the repository and repairs a plan.

#### Scenario: The prompt of the review
- **WHEN** refine builds the request of the review
- **THEN** the client has no tool, and the instructions of the review name no tool and no repair round

### Requirement: Refine shows a tag of the model's text as text
Outside code, refine SHALL change the `<` of each tag of the model's text into `&lt;`. So the tag shows as text with all its words. A `<` that an odd number of backslashes escapes SHALL stay as it is. Refine SHALL do the same again after it rewrites the links. The rewrite can build a tag or an opener from the text around a label.

#### Scenario: A tag outside code
- **WHEN** the model's text holds `Use <read command> here`
- **THEN** refine writes `Use &lt;read command> here`, which GitHub shows as the text `Use <read command> here` and reads as no tag

#### Scenario: A tag in a text with a backtick that opens no code span
- **WHEN** the model's text is ```A `` `x` `<b>see</b>` B```, in which GitHub reads `<b>see</b>` as a tag and not as code
- **THEN** refine writes ```A `` `x` `&lt;b>see&lt;/b>` B```, which holds no raw tag

#### Scenario: A tag that the rewrite of a link builds
- **WHEN** the model's text is `<[b>](https://example.com/a)`, or a link whose label is `!-- devops-roadmap-record {"Status": "Ready"} --` after a `<`
- **THEN** refine writes `&lt;b> (`https://example.com/a`)`, and for the record block it writes text with no comment opener

#### Scenario: A tag that a backslash escapes
- **WHEN** the model's text is `\<b>x`, or `\\<b>x` with two backslashes
- **THEN** refine writes `\<b>x`, which GitHub shows as the text `<b>x`, and `\\&lt;b>x`

#### Scenario: Angle-bracket text in a code span
- **WHEN** the model's text is ``Keep `<section>.<option>` as it is`` or ``Run `devops <read command> --help` now``
- **THEN** refine writes the text as it is

### Requirement: Refine shows no raw HTML in the model's text
The text that refine writes from the model's text SHALL hold no tag, comment, declaration or processing instruction that GitHub reads as HTML. This SHALL hold whatever the text holds. It SHALL hold also for a text with a backtick that opens no code span. It SHALL hold for a link whose rewrite builds a tag, and for many tags that hold a backtick. The time that refine takes SHALL grow in proportion to the length of the text.

#### Scenario: A tag with a backtick
- **WHEN** the model's text is ```<a title="`">`<b>` ```
- **THEN** refine writes text that the Markdown parser reads with no raw HTML

#### Scenario: Many tags with a backtick
- **WHEN** the model's text is ```<a title="`">` ``` 400 times, then ```<b>` ```
- **THEN** refine writes text that the Markdown parser reads with no raw HTML, in a time in proportion to the length of the text

### Requirement: The model reads the reason of a rejected plan
The comment of a rejected plan SHALL be a comment of the stage job. It SHALL stay out of `replies`, and `stage_return` SHALL hold its reason, without the marker of the stage job and without the marker of a rejected plan. Refine SHALL give the item one new look after the comment, as it does after any other return of the stage job.

#### Scenario: The request after a rejected plan
- **WHEN** the stage job commented the reason of a rejected plan and returned the item to New, and refine looks at the item
- **THEN** `stage_return` holds the reason, holds no marker, and `replies` is empty

### Requirement: The prompts of refine name the reason of a rejected plan
The prompts of the proposal and of the investigation SHALL say that the reason in `stage_return` can be the reason of a person who rejected a plan, and that the item must not become Ready again with the same proposal.

#### Scenario: The prompts name the case
- **WHEN** a test reads the two prompts
- **THEN** each one names `stage_return` and a rejected plan

### Requirement: A rejected or in-use check adds no question
When the recorded check of an item has the verdict `rejected` or `in-use`, refine SHALL add no question, SHALL NOT set the next step `PERSON` because of the check, and SHALL NOT record `refine.alternatives_asked`. The request SHALL hold the verdict, the tool URL, the block and the job's latest comment of that check under the key `alternatives`, as for any check.

#### Scenario: A rejected check
- **WHEN** refine plans a New item whose recorded check has the verdict `rejected` and a tool, and the item otherwise meets every rule of the Ready check
- **THEN** the item has no open question and refine sets it Ready

#### Scenario: An in-use check
- **WHEN** refine plans a New item whose recorded check has the verdict `in-use` and a tool, and the item otherwise meets every rule of the Ready check
- **THEN** the item has no open question and refine sets it Ready

#### Scenario: The request
- **WHEN** refine plans an item whose recorded check has the verdict `rejected`
- **THEN** the proposal request holds `alternatives` with the verdict `rejected`, the tool URL and the text of the job's comment

### Requirement: A form check failure is a job failure that retries
When the proposal fails a form check, refine SHALL write no body, no comment and no Status. It SHALL record the failed check names in `refine.failed_check` and the count of tries in `refine.tries`. While the count is below `CONST_ROADMAP_REFINE_MAX_TRIES`, it SHALL record the next step `retry`, and a later round SHALL refine the item again. The form checks are `problem_statement`, `existing_tool` and `acceptance_criteria`.

#### Scenario: A proposal with no problem statement
- **WHEN** the model returns a proposal whose problem statement is empty, and the item has no earlier try
- **THEN** the item has no person wait, `refine.next_step` is `retry`, `refine.tries` is `1`, `refine.failed_check` is `problem_statement`, and refine wrote no comment

#### Scenario: The next round tries again
- **WHEN** a round follows a failed try and nothing changed in the item
- **THEN** the round selects the item and sends one model request for it

### Requirement: A passing proposal clears the job failure
A proposal that passes the form checks with no job failure SHALL clear `refine.tries`, `refine.failed_check` and `refine.failure` from the job record.

#### Scenario: A later proposal passes
- **WHEN** the model returns a whole proposal after a failed try
- **THEN** the item is refined as before, and its record holds no `refine.tries`, `refine.failed_check` or `refine.failure`

### Requirement: A job failure at the try limit waits on a body edit
When the count of tries reaches `CONST_ROADMAP_REFINE_MAX_TRIES`, refine SHALL record the next step `failed`, and a round SHALL send no model request for the item until a person edits its body.

#### Scenario: The limit is reached
- **WHEN** a proposal fails the same form check on the third round and the limit is 3
- **THEN** `refine.next_step` is `failed`, `refine.tries` is `3`, and the next round sends no model request for the item

#### Scenario: A body edit
- **WHEN** a person edits the body of an item whose next step is `failed`
- **THEN** the next round selects the item, and its count of tries starts at 1

### Requirement: A source question is answered with the read tools or reports what they searched
When a question has no verified source after the investigation, refine SHALL treat it as a job failure with the failed check `missing_source`, and SHALL record in `refine.failure` the calls of the read tools that the investigation made. The item SHALL NOT wait on a person for it.

#### Scenario: A read tool finds the source
- **WHEN** the first proposal answers "Where is the sample function?" as a fact with no source, and the investigation reads `src/sample.py`
- **THEN** the item has no open question and no job failure

#### Scenario: No tool finds the source
- **WHEN** the investigation searches for a text that the repository does not hold and answers with no source
- **THEN** the item has the next step `retry`, `refine.failed_check` is `missing_source`, and `refine.failure` names the search call and its text

### Requirement: The report counts the items that go on without a person
The refine plan report SHALL show the number of items of the round whose next step is `ready`, `blocked` or `retry`, and SHALL list each one.

#### Scenario: A round with a Ready item, a person question and a retry
- **WHEN** a round refines one item to Ready, one item with a `(a person decides)` question and one item whose proposal fails a form check
- **THEN** the report states that 2 items go on without a person and lists the Ready item and the retry item

### Requirement: The issue listing gives the count of comments
The roadmap store SHALL give each `Item` the count of comments on its issue as `comments`, as the issue listing carries it. A write to the body or the labels of the issue SHALL NOT change the count.

#### Scenario: Comments of a person
- **WHEN** a person writes two comments on an issue, and a job then writes a mark in its job record
- **THEN** the Item of the issue has `comments` 2

### Requirement: A read of the comments of a waiting item is recorded
When a round reads the comments of an item that waits and finds no reply, `--confirm` SHALL record `refine.comments_seen` (the count of the listing), `refine.commented_at` (the time of refine's last comment) and `refine.wait_refs` (the issues, then the paths, that the wait text names). A round that finds the same values in the record SHALL write nothing for the item.

#### Scenario: A wait on a person that names an issue and a path
- **WHEN** an item waits on a person, the text of refine's comment names issue 3 and the path `src/sample.py`, and a round runs with `--confirm`
- **THEN** the job record holds `refine.comments_seen` `1`, `refine.commented_at` with the time of refine's comment, and `refine.wait_refs` `#3,src/sample.py`

### Requirement: An unchanged waiting item costs no comment read
Without `--item`, a round SHALL read no comment of an item that waits on a blocker or on a person, whose body is unchanged and whose count of comments is the recorded `refine.comments_seen`. The item SHALL keep waiting on its next step, and the round SHALL make no model call for it.

#### Scenario: A second round after the record
- **WHEN** an item waits on an open blocker, and a round has recorded the read of its comments
- **THEN** the next round lists the item as waiting on its blocker, reads no comment of the item and makes no model call

### Requirement: The exits of a wait need no comment read
A round SHALL end the wait of an item whose count of comments is the recorded one, with no read of its comments, when every recorded blocker is closed, when a commit on the default branch changed a recorded `refine.block_paths` path at or after `refine.commented_at`, or, for a wait on a person, when an issue or a path of `refine.wait_refs` closed or changed after `refine.commented_at`. The `updated_at` of the item SHALL NOT be part of the check.

#### Scenario: A blocker closes
- **WHEN** a recorded wait holds a blocker, and a person closes the blocker
- **THEN** the next round refines the item, and the `updated_at` of the item is the one it had before

#### Scenario: A cited path changes
- **WHEN** a recorded wait cites `src/sample.py`, and a commit changes that path five minutes after `refine.commented_at`
- **THEN** the next round refines the item, and the `updated_at` of the item is the one it had before

### Requirement: A new comment ends the saving
A round SHALL read the comments of an item that waits when its count of comments differs from the recorded one. A reply since refine's last comment SHALL end the wait. A comment that is no reply SHALL cost one read, and the round SHALL record the new count.

#### Scenario: A reply
- **WHEN** a person replies to the comment of an item that waits on a person with a recorded wait
- **THEN** the next round reads the comments of the item and refines it

#### Scenario: A comment of another job
- **WHEN** the alternatives job comments on an item with a recorded wait
- **THEN** the next round reads the comments of the item once and keeps it waiting, and the round after it reads none

### Requirement: The dry run lists the record of a waiting item
The dry-run plan of a round without `--item` SHALL list the read of the issue and the write of its job record under the condition that the round read the comments of the waiting item and its job record does not hold what they gave. The plan with `--item` SHALL list none.

#### Scenario: The plan of a round
- **WHEN** `devops roadmap refine --dry-run` plans a round without `--item`, and a round with `--item 7`
- **THEN** only the first plan lists the record of the waiting item

### Requirement: A round writes each item when the item is done
The refine round of the Service SHALL write the result of each item as soon as that item is done, before it takes the next item, so a stop of the Service loses at most the item in progress and the next round takes the items that are not written.

#### Scenario: Round of three items stops in the plan of item three
- **WHEN** A refine round of 3 items stops in the plan of item 3.
- **THEN** Items 1 and 2 carry their refine result, item 3 stays New, and the next round takes item 3 first.

### Requirement: Plan without a writer writes nothing
`plan_refine` SHALL write nothing to any item when the caller gives it no writer.

#### Scenario: Plan run with no writer
- **WHEN** `plan_refine` runs on a round of 3 items with no writer.
- **THEN** The store receives no write, and the 3 items stay New.

### Requirement: A failed write does not stop the round
The refine round SHALL log a write that fails for one item, count the item as failed, write the other items, and fail at its end with the number of each item that it could not write.

#### Scenario: Write of item two fails
- **WHEN** The write of the body of item 2 fails in a round of 3 items.
- **THEN** Items 1 and 3 are written, item 2 stays New, and the round raises an error that names item 2.

### Requirement: A round logs its start and its end
The refine round SHALL log one line at its start and one line at its end, and the end line SHALL give the counts of items taken, written and failed.

#### Scenario: Round with one failed write
- **WHEN** A refine round takes 3 items, writes 2 and fails 1.
- **THEN** The log holds one start line with 3 items taken and one end line with taken=3, written=2 and failed=1.

### Requirement: The plan says when web search is off for want of a provider
When refine had no web search in a round, the plan SHALL say so once, with the reason: the repository is private, its visibility could not be read, or no search provider is configured.

#### Scenario: No search provider
- **WHEN** refine plans a round on a public repository whose providers are all unconfigured
- **THEN** the report says that web search is off because no search provider is configured

#### Scenario: The keyless provider
- **WHEN** refine plans a round on a public repository with the default providers and no Firecrawl key
- **THEN** web search is on

### Requirement: Refine writes the result of an item with one request
Refine SHALL write the new body, the marks of the job record and the Status of one item with one `PATCH` of the issue, and the comment as a separate request after it. A stop of the Service after the write SHALL leave the new body, the new marks and the new Status together, so the next round SHALL make no model call for the item. The dry-run plan SHALL list one read of the issue and one `PATCH` for the body with the marks, and no separate write of the body.

#### Scenario: A stop after the only write of a Ready item
- **WHEN** a refine round sets a New item Ready and the Service stops right after the write of the item
- **THEN** the item has the refined body, the Status Ready and the marks of the round, and the next round refines no item and makes no model call

#### Scenario: An item that keeps its Status
- **WHEN** refine leaves a New item New with a question for a person
- **THEN** refine makes one write of the issue that holds the new body and the marks, and one comment

#### Scenario: A Ready item goes back to New
- **WHEN** refine finds a Ready item not ready
- **THEN** refine makes one write of the issue that holds the new body, the Status New and the marks, and one comment

#### Scenario: The dry-run plan of a refine round
- **WHEN** `devops roadmap refine --dry-run` plans a round, and a round with `--item 7`
- **THEN** each plan lists one read of the issue and one `PATCH` that carries the body and the labels, and neither plan lists a separate write of the body

### Requirement: A failed model call records its class and waits
When the model call of an item fails, refine SHALL record `refine.failed_at`, `refine.failed_step` (`investigate`) and `refine.failed_class` (the class of the error) in the job record, in the same marks write as the failed body hash when the item's text caused the failure. A placeholder failure SHALL record nothing. A round without `--item` SHALL leave the item out until `refine.failed_at` plus the wait of its class, and SHALL take the other items.

#### Scenario: A timeout
- **WHEN** the gateway answers an item with a timeout
- **THEN** the job record holds the time, the step `investigate` and the class `provider`, it holds no failed body hash, and one marks write made them

#### Scenario: The wait has not passed
- **WHEN** the next round runs 59 minutes after a `provider` failure
- **THEN** it sends no request for the item, lists it as waiting with the step `retry`, and refines the other items

#### Scenario: The wait has passed
- **WHEN** the next round runs 1 hour after a `provider` failure
- **THEN** the round takes the item again

#### Scenario: A reply that never validates
- **WHEN** a reply never validates, and the round runs 5 hours 59 minutes later and then 6 hours later
- **THEN** the job record holds the class `parser` and the failed body hash from one write, the first round sends no request, and the second takes the item

#### Scenario: A record with no usable class
- **WHEN** the job record holds `refine.failed_at` and no class, or a class that is no failure class, or a class with no wait
- **THEN** the item waits as `ci_infra`, and a time that is no time holds the item for no time

#### Scenario: A person overrules the wait
- **WHEN** a person runs refine with `--item` for an item that waits
- **THEN** the round refines the item

#### Scenario: A body edit
- **WHEN** a person edits the body of an item after a failure that its text caused
- **THEN** the next round takes the item

#### Scenario: The second failure on the same body
- **WHEN** a second reply on the same body never validates
- **THEN** the item waits on a body edit and the three keys are cleared

### Requirement: A round whose model call worked clears the failed class
A round whose model call worked SHALL clear `refine.failed_at`, `refine.failed_step` and `refine.failed_class` from the job record, whether the round refined the item or ended in a job failure.

#### Scenario: A success after a timeout
- **WHEN** a round refines an item whose record holds the three keys
- **THEN** the record holds none of them

#### Scenario: A form check fails after a timeout
- **WHEN** a round gets a proposal that fails a form check for an item whose record holds the three keys
- **THEN** the record holds `refine.tries` and none of the three keys

### Requirement: Refine leaves an item with an unlisted title type
`devops roadmap refine` SHALL NOT refine an item whose title type is not in `CONST_BRANCH_TYPES`, also with `--item`, and SHALL make no model call for it, so the item does not become Ready. The detail SHALL name the type and `invalid-title-type`. The item SHALL wait on a person when the type has no correction. The first round after a title with a listed type SHALL refine the item.

#### Scenario: A New item with a security title
- **WHEN** a round runs over a New item titled `security(ssh): verify node host keys`
- **THEN** the model records no request, the Status stays New, and the detail names `fix(security): verify node host keys` and `invalid-title-type`

#### Scenario: A type with no correction
- **WHEN** a round runs over a New item titled `wip(cli): finish the half-done work`
- **THEN** the item waits on a person, the detail names `wip`, and the model records no request

#### Scenario: The title gets a listed type
- **WHEN** the title of the security item becomes `fix(security): verify node host keys` and a round runs
- **THEN** refine refines the item and sets it Ready

#### Scenario: A person names the item with --item
- **WHEN** refine runs with `--item` for the item titled `wip(cli): finish the half-done work`
- **THEN** the model records no request, and the Status stays New

#### Scenario: The limit of a round
- **WHEN** a round with `--limit 1` runs over the `wip(cli)` item and a New item with a listed type
- **THEN** refine takes the item with the listed type

### Requirement: Refine reads a dependency that the body names by its title
Refine SHALL add to the dependencies of a proposal each issue that the Dependencies section of the body names by a quoted Conventional Commit title: the one open Item with that exact title, else the one closed Item with it. A list item that names `#N` SHALL name its issue by the number. A title that names no Item or two Items SHALL fail the round with the job check `dependencies`, and the error SHALL ask for `#<number>`.

#### Scenario: An open issue named by its title
- **WHEN** the Dependencies section names the quoted title of an open issue and the proposal names no dependency
- **THEN** the item has the next step `blocked` with that issue, and the refine section lists the issue under Dependencies

#### Scenario: A closed issue named by its title
- **WHEN** the Dependencies section names the quoted title of a closed issue
- **THEN** the item reaches Ready, and the refine section lists the issue under Dependencies

#### Scenario: A title that names no single issue
- **WHEN** the Dependencies section names a quoted title that no issue has, or that two open issues have
- **THEN** the item has the next step `retry`, `refine.failed_check` is `dependencies`, `refine.failure` names the title and asks for `#<number>`, and refine wrote no comment

#### Scenario: Quoted text that is no title, and an item with a number
- **WHEN** the Dependencies section holds a quoted tool name, and a list item that names `#N` and a title that no issue has
- **THEN** the round has no job failure

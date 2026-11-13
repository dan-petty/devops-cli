# roadmap-refine/writes Specification

## Purpose
What a refine round writes to GitHub: the safe text of the model, the body hash, the result of each item in one request, the warnings, the logs and the report.

## Requirements

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

### Requirement: The report counts the items that go on without a person
The refine plan report SHALL show the number of items of the round whose next step is `ready`, `blocked` or `retry`, and SHALL list each one.

#### Scenario: A round with a Ready item, a person question and a retry
- **WHEN** a round refines one item to Ready, one item with a `(a person decides)` question and one item whose proposal fails a form check
- **THEN** the report states that 2 items go on without a person and lists the Ready item and the retry item

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

### Requirement: A refine round skips an item that changed since the read
A refine round in the Service SHALL NOT write the body, the marks or the Status of an item that a person or another job changed between the read and the write, and SHALL NOT fail for it. The next round SHALL read the item again. The change is a write that the store refuses with `RoadmapItemChangedError`, or a body outside the refine section that changed.

#### Scenario: The Status of an item changes during the round
- **WHEN** a person moves item 2 of 3 to Blocked while the model works on it
- **THEN** items 1 and 3 are written, item 2 gets no write and one INFO line, the round ends with `taken=3`, `written=2` and `failed=0` and raises no error, and the next round takes item 2 again

#### Scenario: Another write failure
- **WHEN** the write of item 2 fails with another `GitHubOperationError`
- **THEN** the round raises `RoadmapRefineError` that names item 2

### Requirement: A skipped item writes no result line
A refine round SHALL write no `roadmap job result` line for an item that changed since the read, as an alternatives check whose body changed writes none, and SHALL NOT count the item as written or as failed.

#### Scenario: The store refuses the write of a changed item
- **WHEN** the store refuses the write of item 2 with `RoadmapItemChangedError`
- **THEN** the round logs no result line for item 2

#### Scenario: The body of an item changes during the round
- **WHEN** a person edits the body of item 2 while the model works on it
- **THEN** item 2 stays New, the round logs no result line for item 2, and the round ends with `written=2`

#### Scenario: A write that fails for another reason
- **WHEN** the write of item 2 fails with another `GitHubOperationError`
- **THEN** the result line of item 2 holds `result=error` and `success=false`

# roadmap-refine/waits Specification

## Purpose
How a refined item waits: the paths and the blockers that cause a block, the end of a wait, and the reads of the comments of a waiting item.

## Requirements

### Requirement: Refine records the paths that cause a block
When refine leaves an item New with an open dependency or a suspected block, it SHALL record in the job record, as `refine.block_paths`, the paths of the proposal's `block_paths` that the checkout holds at the refined commit: each path one time, without its line, at most five, and none outside the repository. It SHALL record no path for a proposal with no open dependency and no suspected block.

#### Scenario: A proposal cites paths that the checkout holds and paths that it does not hold
- **WHEN** the proposal of a New item has a suspected block, and its `block_paths` are `src/sample.py:1`, `src/missing.py`, `../CONTEXT.md`, `/etc/hosts`, `src/sample.py` and `CONTEXT.md`, and the checkout holds `src/sample.py` and `CONTEXT.md`
- **THEN** the job record holds `refine.block_paths` `src/sample.py,CONTEXT.md`

#### Scenario: A proposal with no block
- **WHEN** the proposal of a New item gives `block_paths` `src/sample.py` and has no suspected block and no dependency
- **THEN** the job record holds no `refine.block_paths`

### Requirement: A change to the code that a block cites ends the wait
Without `--item`, `devops roadmap refine` SHALL look at an unchanged waiting item again when a commit on the default branch changed one of its recorded `refine.block_paths` at or after the start of the wait: the later of refine's last comment on the item and `refine.repeated_at`. When no recorded path changed at or after that start, the item SHALL keep waiting on its next step, and the round SHALL make no model call for it.

#### Scenario: The cited path changes after refine's last comment
- **WHEN** an item waits on an open blocker, or on a suspected block, with `refine.block_paths` `src/sample.py`, and a commit on the default branch changes `src/sample.py` five minutes after refine's last comment on the item
- **THEN** the next round refines the item again, with one model call, and the item is not waiting

#### Scenario: The cited path does not change after refine's last comment
- **WHEN** an item waits on an open blocker with `refine.block_paths` `src/sample.py`, the newest commit that changed `src/sample.py` is one day before refine's last comment, and a later commit changes only `CONTEXT.md`
- **THEN** the next round leaves the item waiting on its blocker and makes no model call

#### Scenario: The dry-run plan of a round
- **WHEN** `devops roadmap refine --dry-run` plans a round without `--item`, and when it plans a round with `--item 7`
- **THEN** the round's plan lists one read of the newest commit that changed each cited path of a waiting item, under the condition that no reply follows the start of the wait, and the plan with `--item` lists no such read

#### Scenario: A cited path that changed before a round with no comment
- **WHEN** a commit changes the cited path of a waiting item, the look that it starts finds the same wait and posts no comment, and two more rounds run
- **THEN** the change gave one model call, and the item holds one refine comment

### Requirement: A second stage return on the same body waits on a person
A round that refines an unchanged item after a stage return SHALL record its body hash in `refine.returned_body_hash`. Any other round SHALL clear the key. An item whose `refine.returned_body_hash` equals its `refine.body_hash` and that the stage job returned again SHALL wait on a person, with the reason that the job returned it twice on the same body, and with no model call. A reply or a body edit SHALL end that wait.

#### Scenario: The second return
- **WHEN** refine set an item Ready, the stage job returned it, refine looked again and set it Ready, and the stage job returned it again
- **THEN** the item waits on a person with the reason "The stage job returned the item to New twice on the same body. A reply or a body edit makes refine look at it again." and the round makes no model call

#### Scenario: A body edit between two returns
- **WHEN** a person edits the body of an item after its first return
- **THEN** the next round refines the item and clears `refine.returned_body_hash`

### Requirement: A wait on a person ends when a cause that its text names ends
Without `--item`, `devops roadmap refine` SHALL look again at an unchanged item that waits on a person when an issue that the wait text names closed, or a file that it names and the tree of the round holds changed on the default branch, at or after the start of the wait. The wait text SHALL be the Open questions, Suspected block and Watched files of the refine section and the replies that the rounds read. An issue that closed before, an issue of another repository and the item SHALL end no wait.

#### Scenario: A named issue closes after the comment
- **WHEN** an item waits on a person, an open question of its refine section asks about #12, and #12 closes after refine's last comment
- **THEN** the next round refines the item again

#### Scenario: A named issue closed before the comment
- **WHEN** an open question of the refine section names #12 and #12 closed before refine's last comment
- **THEN** the item keeps waiting and the round makes no model call

#### Scenario: A named file changes with no recorded block path
- **WHEN** an item waits on a person with no `refine.block_paths`, an open question of its refine section names `src/sample.py`, and a commit on the default branch changes that file after refine's last comment
- **THEN** the next round refines the item again

#### Scenario: A reply names the issue
- **WHEN** the refine section names no issue, a reply that the round read names #12, and #12 closes after refine's last comment
- **THEN** the next round refines the item again

### Requirement: An open dependency outside a cycle blocks the item
`devops roadmap refine` SHALL give an item the next step `blocked` when its validated proposal has no open question, fits one pull request and names a dependency that gives an open blocker (the rule of `roadmap-dependency-cycle`), and no dependency leads back to the item. It SHALL record the open blockers and SHALL NOT set the Status to Ready. A Ready item SHALL go back to New. A closed dependency and the parent tracker SHALL NOT hold the item back.

#### Scenario: A complete proposal with one open dependency
- **WHEN** a New item has a complete proposal with one open dependency (no open question, no split, no suspected block)
- **THEN** the next step is `blocked` with that issue, the refine record holds its number, and the item stays New

#### Scenario: A Ready item with an open dependency
- **WHEN** the proposal of a Ready item meets the same conditions, and a person runs refine for the item with `--item`
- **THEN** the item goes back to New, with the next step `blocked` and its number in the refine record

#### Scenario: A closed dependency
- **WHEN** a New item has a complete proposal with one closed dependency (no open question, no split, no suspected block)
- **THEN** the next step is `ready`, the refine record holds no blocker, and the item is Ready

#### Scenario: The parent tracker as the one dependency
- **WHEN** a New item has a complete proposal whose one dependency is the open parent tracker of the item
- **THEN** the next step is `ready`, the refine record holds no blocker, and the item is Ready

#### Scenario: Another tracker as the one dependency
- **WHEN** a New item has a complete proposal whose one dependency is another open tracker with the open sub-issues B and C
- **THEN** the next step is `blocked` with `#B` and `#C`, and the refine record holds `B,C`

### Requirement: The last blocker to close ends the block
A blocked item SHALL wait while the issues that its record names give an open blocker (the rule of `roadmap-dependency-cycle`), with no model call. The round after the last blocker closes, or after the last recorded issue stops being a blocker, SHALL refine the item again. A recorded issue that is now the parent tracker of the item SHALL end the wait, and a recorded issue that is now another tracker SHALL give the wait its open sub-issues. `devops roadmap explain` SHALL give the same wait.

#### Scenario: The last blocker closes
- **WHEN** an item waits on two open dependencies, one of them closes, and then the other closes
- **THEN** the round after the first close leaves the item waiting on the second, with no model call. The round after the second close refines the item with one model call and sets it Ready

#### Scenario: The recorded blocker is now the parent tracker
- **WHEN** a round recorded the item as blocked on an open issue, and that issue is now the parent tracker of the item
- **THEN** `refine_left_out` gives no wait, and the next round refines the item and sets it Ready

#### Scenario: The recorded blocker is now another tracker
- **WHEN** a round recorded the item as blocked on an open issue, and that issue is now a tracker with the open sub-issues B and C
- **THEN** the next round leaves the item waiting on `#B` and `#C` with no model call, and `refine_left_out` names `#B, #C`

### Requirement: A read of the comments of a waiting item is recorded
When a round reads the comments of an item that waits and finds no reply, `--confirm` SHALL record `refine.comments_seen` (the count of the listing), `refine.commented_at` (the time of refine's last comment) and `refine.wait_refs` (the issues, then the paths that the tree of the commit of the round holds, that the wait text names). A round that finds the same values in the record SHALL write nothing for the item.

#### Scenario: A wait on a person that names an issue and a path
- **WHEN** an item waits on a person, an open question of its refine section names issue 3 and the path `src/sample.py`, and a round runs with `--confirm`
- **THEN** the job record holds `refine.comments_seen` `1`, `refine.commented_at` with the time of refine's comment, and `refine.wait_refs` `#3,src/sample.py`

### Requirement: An unchanged waiting item costs no comment read
Without `--item`, a round SHALL read no comment of an item that waits on a blocker or on a person, whose body is unchanged, whose count of comments is the recorded `refine.comments_seen`, and whose recorded `refine.wait_refs` holds no path that the tree of the commit of the round lacks. The item SHALL keep waiting on its next step, and the round SHALL make no model call for it.

#### Scenario: A second round after the record
- **WHEN** an item waits on an open blocker, and a round has recorded the read of its comments
- **THEN** the next round lists the item as waiting on its blocker, reads no comment of the item and makes no model call

### Requirement: The exits of a wait need no comment read
A round SHALL end the wait of an item whose count of comments is the recorded one, with no read of its comments, when every recorded blocker is closed, when a commit on the default branch changed a recorded `refine.block_paths` path, or, for a wait on a person, when an issue or a path of `refine.wait_refs` closed or changed. Only a change at or after the later of `refine.commented_at` and `refine.repeated_at` SHALL count. The `updated_at` of the item SHALL NOT be part of the check.

#### Scenario: A blocker closes
- **WHEN** a recorded wait holds a blocker, and a person closes the blocker
- **THEN** the next round refines the item, and the `updated_at` of the item is the one it had before

#### Scenario: A cited path changes
- **WHEN** a recorded wait cites `src/sample.py`, and a commit changes that path five minutes after `refine.commented_at`
- **THEN** the next round refines the item, and the `updated_at` of the item is the one it had before

### Requirement: A new comment ends the saving
A round SHALL read the comments of an item that waits when its count of comments differs from the recorded one. A reply at or after the start of the wait, the later of refine's last comment and `refine.repeated_at`, SHALL end the wait. A comment that is no reply SHALL cost one read, and the round SHALL record the new count.

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

### Requirement: A person wait that older rules set gets one new look
A round that writes a proposal SHALL record `CONST_ROADMAP_REFINE_RULES_SINCE` as `refine.rules`. A round SHALL refine an unchanged item that waits on a person when its `refine.rules` is older than that constant, or, when the record holds none, when refine's last comment is older. A wait on a person that the current rules set SHALL stay.

#### Scenario: A wait from before the rules
- **WHEN** an item waits on a person since a refine comment older than the rules, its record holds no version, and its body is unchanged
- **THEN** the next round refines it and records the current version, and a round after it that gets the same question again makes no model call

#### Scenario: A wait with the current version
- **WHEN** an item waits on a person, and its record holds the current version while refine's comment is older than the rules
- **THEN** the next round leaves it waiting on a person and makes no model call

### Requirement: A dependency cycle gives a person step that names it
`devops roadmap refine` SHALL give an item the next step `person` when a dependency of the item leads back to the item, before the step that its proposal gives. The detail of the step SHALL name the full cycle, and refine's section SHALL name the cycle under its Suspected block heading. The round SHALL record no open issue as a blocker for that item.

#### Scenario: Two items in a cycle
- **WHEN** a refine round reads a store where the record of A names B and the Dependencies section of B names A, and each proposal is complete
- **THEN** the step of A and of B is `person`, each detail names its cycle, no open issue is a blocker of either, and each refine section names the cycle under its Suspected block heading

### Requirement: A cycle keeps an item out of Ready and ends its wait
Refine SHALL NOT set the Status to Ready for an item in a cycle, and a Ready item in a cycle SHALL go back to New. A round SHALL end the recorded wait of an item whose record holds the step `blocked` when that item is in a cycle, and `devops roadmap explain` SHALL give the answer that the round gives.

#### Scenario: The Status of an item in a cycle stays New
- **WHEN** a refine round finds item A in a cycle whose proposal passes every form check
- **THEN** the step of A is `person` and the Status of A stays New, so the stage job takes no Ready item that a cycle holds back

#### Scenario: The recorded wait of a blocked item in a cycle ends
- **WHEN** a refine round finds item A whose record holds the step `blocked` on the open item B, and the record of B or its Dependencies section names A
- **THEN** the round refines A and records the step `person` with the cycle

#### Scenario: Explain ends the wait that the round ends
- **WHEN** a person runs `devops roadmap explain` for item A whose record holds the step `blocked` on the open item B, and the record of B or its Dependencies section names A
- **THEN** the refine line of the output says that refine takes the item, and names no wait on the open issue

### Requirement: An issue reference under Dependencies names a blocker
Refine SHALL read each `#N` under the Dependencies heading of the body as a dependency of the proposal, also in a sentence of prose, unless the requirement "A link under Dependencies names no blocker" leaves it out.

#### Scenario: A blocker list item, a line of references and a Merge first line
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the list item `- #4989`, the paragraph `#5134, #5135` and the paragraph `Merge first: #5136`
- **THEN** `body_dependencies` returns `[4989, 5134, 5135, 5136]` in the order of the section

#### Scenario: A paragraph that opens with references and goes on in prose
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraph `#4884, #4889, #3917. The scheduled reindex waits for #4566.`
- **THEN** `body_dependencies` returns `[4884, 4889, 3917, 4566]`

#### Scenario: A Depends on line
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraph `Depends on #5356. The acceptance needs the running server.` and then the paragraph `It does not wait for #5343.`
- **THEN** `body_dependencies` returns `[5356]`

#### Scenario: A blocker in a sentence that opens with other words
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraphs `#5421 (merged first).` and `Open the pull request after the pull request of #5234 merges.`
- **THEN** `body_dependencies` returns `[5421, 5234]`

#### Scenario: The hold line of the freeze
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds as its first item `- #6521 (hold: incremental work on the stage, implement and fix-checks jobs waits for the re-architecture of #6519)`
- **THEN** `body_dependencies` returns `[6521]`

### Requirement: A link under Dependencies names no blocker
Refine SHALL read no dependency from a block that starts with `None` or `No`, from a `#N` after a link word of its sentence (`Part of`, `Child`, `Tracker`, `Related`, `Source` or an owner decision), from a sentence with a reverse phrase such as `needs this item`, `this item blocks` or `is the parent`, from a block whose issue merges in either order, or from a `#N` in parentheses with other words. A sentence ends at `.`, `;`, `!`, `?` or a line end.

#### Scenario: A source line after None
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds `None.` and then `Source: #4989` as a separate paragraph
- **THEN** `body_dependencies` returns an empty list

#### Scenario: A parent, a child, a related issue and a reverse link
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraphs `Part of #5014`, `Child 5 of #4893`, `Related: #4408`, `#4691 needs this item` and `This item blocks #5134 step 6`
- **THEN** `body_dependencies` returns an empty list

#### Scenario: A blocker and a reverse sentence in one paragraph
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraph `#4550 puts the dependencies of the catalog first. #4691 needs this item.`
- **THEN** `body_dependencies` returns `[4550]`

#### Scenario: A parent after a blocker, a parent tracker and a merge in either order
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds the paragraph `Merge first: #4835, child 8 of #4833.` and the list items `- #4517 is the parent tracker.` and `- #6347 (open): changes the verdict too. Rebase before the second of the two merges.`
- **THEN** `body_dependencies` returns `[4835]`

### Requirement: A non-blocker mention under Dependencies holds nothing back
The stage job and the implement job SHALL give no reason for an open issue that the body names only as a non-blocker mention under Dependencies. They SHALL name only an open issue that the section names as a blocker.

#### Scenario: An open related issue
- **WHEN** the Dependencies section of a Ready item holds `Related: #4408`, and issue `#4408` is open
- **THEN** the stage job and the implement job give no reason for the item, and neither reason names `#4408`

#### Scenario: An open issue on a Depends on line
- **WHEN** the Dependencies section of a Ready item holds `Depends on #4408`, and issue `#4408` is open
- **THEN** the stage job and the implement job give the reason that names `#4408`

#### Scenario: A held item
- **WHEN** the Dependencies section of an item holds the hold line `- #<hold> (hold: ... of #<tracker>)` and then `Related: #<related>`, and the three issues are open
- **THEN** `open_dependency` gives a reason that names `#<hold>` only

### Requirement: A wait records only the paths that the tree holds
A round SHALL record in `refine.wait_refs` only the paths that the tree of the commit it reads holds, as a file or as a directory that holds a tracked path.

#### Scenario: A decimal, a version, a dotted setting and a domain before two real files
- **WHEN** a wait text names `0.202`, `v1.37.2`, `ai.portkey_url` and `deps.dev` before two files that the tree holds, and `text_paths` reads the text with that tree
- **THEN** the round records the two files in `refine.wait_refs` and none of the four other values

### Requirement: The five-path cap counts only the paths that the tree holds
`text_paths` SHALL apply `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` after it drops the candidates that the tree does not hold, so the first five real paths take the slots.

#### Scenario: Six real files
- **WHEN** a wait text names six files that the tree holds, and `text_paths` reads it with that tree
- **THEN** the round records the first five files and drops the sixth

### Requirement: A path that a period or a comma follows is kept
The cited-path pattern SHALL accept a period or a comma after a path, so `text_paths` finds a file that ends a sentence.

#### Scenario: A sentence ends on a path
- **WHEN** a wait text names a file that the tree holds and a period or a comma follows the path, and `text_paths` reads it with that tree
- **THEN** the round records that file

### Requirement: A value that the tree does not hold costs no commits read
The wait check MUST read no commits for a candidate that the tree does not hold, because the round drops it before it writes `refine.wait_refs`.

#### Scenario: A decimal beside a real file
- **WHEN** a wait text names a decimal and a file that the tree holds, and `path_changed_at` reads each recorded path
- **THEN** the store reads the commits of the file and records no read of the decimal

### Requirement: A directory that the tree holds is a watched path
`text_paths` SHALL keep a directory of the tree as a watched path, because a commit changes the files under it.

#### Scenario: A directory that holds a file
- **WHEN** a wait text names a directory and the tree holds a file under that directory, and `text_paths` reads it with that tree
- **THEN** the round records the directory

### Requirement: The explain verdict reads the tree of the default branch
`devops roadmap explain` SHALL give `refine_left_out` the tracked paths of `origin/<default>`, which it fetched, so it gives the verdict that a round of the Service gives (#3483), whatever branch the clone holds.

#### Scenario: A person asks why an item waits
- **WHEN** a person runs `devops roadmap explain` on an item whose wait text names a real path and a decimal
- **THEN** the verdict reads the real path alone, through `refine_left_out`

#### Scenario: The clone holds another branch
- **WHEN** a wait names a file that `origin/main` holds and the `HEAD` of the clone does not, and a commit changed that file after the start of the wait
- **THEN** `devops roadmap explain` says that refine takes the item

### Requirement: Each path of a run of paths is kept
The cited-path pattern SHALL leave the separator after a path to the next path, so `text_paths` finds each path of a run of paths that one space each separates.

#### Scenario: Four paths in a row
- **WHEN** a wait text reads `Read a.py b.py c.py d.py` and `text_paths` reads it with no tree
- **THEN** `text_paths` gives `a.py`, `b.py`, `c.py` and `d.py`

### Requirement: A record that holds a path that the tree lacks is read again
A round SHALL read as not current a recorded `refine.wait_refs` that holds a path that the tree of its commit lacks. The round SHALL read the comments of the item once, record the references that the tree filter keeps, read no commits of a value that the tree lacks, and make no model call for an item that still waits.

#### Scenario: A record written before the tree filter
- **WHEN** an item waits on a person, its count of comments is the recorded `refine.comments_seen`, and its recorded `refine.wait_refs` is `0.202,src/sample.py`, which a round wrote before the tree filter
- **THEN** the next round records `refine.wait_refs` `src/sample.py`, reads no commits of `0.202` and makes no model call, and the round after it reads no comment of the item

### Requirement: A file that the tree of the round does not hold ends no wait
A round SHALL end no wait for a path of the wait text that the tree of its commit does not hold, so a file that a later commit creates, or that a commit deleted after the record, ends no wait. A person who expects such a file SHALL reply in a comment, which ends the wait.

#### Scenario: A named file that the tree does not hold
- **WHEN** an item waits on a person, an open question of its refine section names `src/sample.py`, the tree of the round does not hold that file, and a commit changes it after refine's last comment
- **THEN** the item keeps waiting and the round makes no model call

### Requirement: A job block marker ends the Dependencies section
Refine SHALL read the Dependencies section of the body up to the next heading of the same or a higher level, or up to an HTML block that is the start or the end marker of a job block (`devops-roadmap-refine` or `devops-roadmap-alternatives`), whichever comes first. A heading inside a job block SHALL start a section. A marker in a code span or inside a paragraph SHALL NOT end the section.

#### Scenario: An alternatives block after the Dependencies section
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds `None.`, and the next line, with no heading between, is the start marker of an alternatives block whose Lacks list holds `- Two-container template integration that #5506 adds`
- **THEN** `body_dependencies` returns an empty list

#### Scenario: The Dependencies part of the refine block
- **WHEN** `body_dependencies` reads a body with no Dependencies heading outside the refine block, the `### Dependencies` part of the refine block holds `- #4989` and is the last part of the block, and an alternatives block whose Lacks list holds `- A tool that #5506 adds` follows the refine end marker
- **THEN** `body_dependencies` returns `[4989]`

#### Scenario: Person text after the refine end marker
- **WHEN** `body_dependencies` reads a body with no alternatives block, the `### Dependencies` part of the refine block holds `- #4989` and is the last part of the block, and the paragraph `Depends on #8888.` follows the refine end marker
- **THEN** `body_dependencies` returns `[4989]`

#### Scenario: A Dependencies section after the end marker of an alternatives block
- **WHEN** `body_dependencies` reads a body that holds an alternatives block whose Lacks list holds `- A tool that #5506 adds`, and after its end marker the heading `## Dependencies` and the list item `- #4989`
- **THEN** `body_dependencies` returns `[4989]`

#### Scenario: A marker in a code span
- **WHEN** `body_dependencies` reads a body whose Dependencies section holds a paragraph that quotes the start marker of an alternatives block in a code span (`CONST_ROADMAP_ALTERNATIVES_START_MARKER`), and then the list item `- #4989`
- **THEN** `body_dependencies` returns `[4989]`

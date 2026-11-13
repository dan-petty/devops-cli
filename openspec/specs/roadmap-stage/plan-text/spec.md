# roadmap-stage/plan-text Specification

## Purpose
The text of a plan: one-line texts, the title and the summary, no placeholder text, the security section of the design, the count of a claimed set, and the build cost of the existing tool.

## Requirements

### Requirement: A text of the proposal, the design and the spec delta stays on one line
The `why`, `what_changes`, `feasibility` and `existing_tool` of the reply, the texts of its decisions and rejected alternatives, and the `purpose`, the names, the texts and the scenario lines of its spec deltas, SHALL be written on one line, and U+FEFF SHALL count as white space. A text at the start of a line SHALL start with no mark of markdown: a heading, a quote, a list marker, a box, a rule, a fence or an HTML tag. The reply that breaks the rule fails the schema.

#### Scenario: A removed section in a requirement
- **WHEN** the `text` of a requirement holds a line break, a heading `## REMOVED Requirements` and a requirement
- **THEN** the `spec.md` of the delta holds the headings Purpose, ADDED Requirements and the one requirement, and no REMOVED section

#### Scenario: A text that starts with a heading
- **WHEN** the `why` of the reply is `## REMOVED Requirements`
- **THEN** the reply fails the schema, and the error says that the text starts with a mark of markdown

#### Scenario: A line break in a bullet
- **WHEN** an item of `feasibility` holds a blank line and a heading
- **THEN** the item is one line

#### Scenario: A mark after U+FEFF
- **WHEN** the `purpose` of a spec is U+FEFF, `##`, U+FEFF and `REMOVED Requirements`
- **THEN** the reply fails the schema

#### Scenario: An HTML tag
- **WHEN** the `existing_tool` of the reply starts with `<pre>`
- **THEN** the reply fails the schema

### Requirement: A plan text is no placeholder
The stage job SHALL refuse a plan whose `why`, `existing_tool`, `feasibility` line, decision or task text is shorter than `PLAN_FIELD_MIN_CHARS` or holds only a placeholder word.

#### Scenario: Short why is refused
- **WHEN** A plan gives `why` as `x`.
- **THEN** `check_proposal` returns a problem that names `why` and the minimum length.

#### Scenario: Placeholder existing tool is refused
- **WHEN** A plan gives `existing_tool` as `todo`.
- **THEN** `check_proposal` returns a problem that names `existing_tool` and the placeholder rule.

#### Scenario: Short feasibility line is refused
- **WHEN** A plan gives a `feasibility` line `x`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and the minimum length.

#### Scenario: A short real sentence is accepted
- **WHEN** A plan gives `why` as `No alternative.`
- **THEN** `check_proposal` returns no placeholder problem for `why`.

#### Scenario: The placeholder rule is the rule of the pull request form
- **WHEN** The content gate judges the text `TBD`.
- **THEN** It refuses the text through `is_placeholder` of `src/devops_cli/roadmap/pull_form.py`.

### Requirement: Existing tool holds a build cost
A plan that sets `builds_own` to true SHALL give a token count and a time in `existing_tool`.

#### Scenario: Build cost missing
- **WHEN** `builds_own` is true and `existing_tool` is `Pydantic can set a minimum length.`
- **THEN** `check_proposal` returns a problem that names `existing_tool` and the cost rule.

#### Scenario: Build cost given
- **WHEN** `builds_own` is true and `existing_tool` is `Cost to build: about 80k tokens and 4 hours.`
- **THEN** `check_proposal` returns no cost problem.

#### Scenario: A plan that adopts a tool needs no cost
- **WHEN** `builds_own` is false and `existing_tool` is `Pydantic covers the need.`
- **THEN** `check_proposal` returns no cost problem.

### Requirement: The summary of a plan is not cut
The stage plan SHALL refuse a `summary` that is longer than `STAGE_SUMMARY_MAX_CHARS` or that ends with `...`.

#### Scenario: Long summary
- **WHEN** A reply gives a `summary` of `STAGE_SUMMARY_MAX_CHARS` plus one characters.
- **THEN** The schema returns a problem that names `summary` and the limit.

#### Scenario: Cut summary
- **WHEN** A reply gives a `summary` that ends with `...`.
- **THEN** The schema returns a problem that names `summary` and the cut rule.

### Requirement: A title holds the full summary
`staging_title` and `delivery_title` SHALL use the full summary and SHALL add no `...`.

#### Scenario: Long delivery summary
- **WHEN** `delivery_title` receives `feat(roadmap): a summary that is longer than the bound of the title`.
- **THEN** The returned title ends with the full summary and holds no added `...`.

#### Scenario: Staging title holds the summary
- **WHEN** `staging_title` receives item 3200 and the summary `Refuse placeholder text`.
- **THEN** The returned title is `docs(openspec): plan #3200 Refuse placeholder text`.

### Requirement: The replay judges a placeholder plan
The stage replay SHALL catch a recorded placeholder plan as a defect of type `other` through the `content` gate.

#### Scenario: Gate lookup
- **WHEN** The replay asks `gate_for(DefectType.OTHER)`.
- **THEN** The answer is `GateName.CONTENT`, not `none` or `pending`.

#### Scenario: Placeholder case replayed
- **WHEN** A golden-set case holds a placeholder in `why` and an `other` defect with the gate `content`.
- **THEN** `replay_case` marks the defect `caught` and reports no failure.

#### Scenario: Placeholder case no longer refused
- **WHEN** The plan of that case holds real text in every field that the content gate reads.
- **THEN** `replay_case` marks the `content` defect `missed` and reports a failure.

### Requirement: The stage job checks the form of the plan title
The stage job SHALL run `title_problems` on the title that it builds for the plan. A reply whose title has a problem SHALL go back to the model with the problems, `roadmap.stage.gate_returns` times at most and one more time when the item gets its extra return (`roadmap-stage/returns`, #4851), and a reply with a problem after the last return SHALL stop the item.

#### Scenario: A summary that repeats plan
- **WHEN** the first reply has the summary `plan the form of a task`
- **THEN** the job sends the problem that names the word `plan` to the model, and the second reply sets the title

#### Scenario: A summary with the issue number
- **WHEN** the reply has the summary `Stop #1 dropping a comment` for issue 1, and each returned reply is the same
- **THEN** the job sends a problem that names `#1`, and the item makes no plan

### Requirement: A title whose summary is over the limit is refused
The stage job SHALL refuse an item whose issue title has a Conventional Commit type and a summary longer than `SUMMARY_MAX_CHARS` UTF-16 code units, counted by `summary_length`.

#### Scenario: A summary of 61 UTF-16 units is refused
- **WHEN** A Ready item has a valid Conventional Commit type and a title summary of 61 UTF-16 code units
- **THEN** The stage job leaves the item out, and its reason names the current length and the limit of 60

#### Scenario: A summary of 60 UTF-16 units passes the length check
- **WHEN** A Ready item has a valid Conventional Commit type and a title summary of 60 UTF-16 code units
- **THEN** The stage job does not refuse the item for the length of its summary

#### Scenario: A title with no type keeps its reason
- **WHEN** A Ready item has a title with no Conventional Commit type and a summary longer than the limit
- **THEN** The stage job leaves the item out and its reason names the missing type, not the length of the summary

### Requirement: A placeholder text is one rule
`is_placeholder` SHALL be true for the texts `x`, `y`, `probe`, `placeholder`, `none`, `ignore`, `pending`, `draft`, `temporary` and "Placeholder not final.", for `__PROBE__`, and for a text that starts with "Not yet:", with no case and no punctuation around the text. `ReplyText` SHALL apply that rule as a validator and SHALL raise the error type `placeholder_text`.

#### Scenario: The filler words
- **WHEN** `is_placeholder` reads `x`, `y`, `probe`, `__PROBE__`, `placeholder` and `none`
- **THEN** it is true for each

#### Scenario: The stub texts of the census
- **WHEN** `is_placeholder` reads `ignore`, `Pending`, `draft`, `temporary` and "Placeholder not final."
- **THEN** it is true for each

#### Scenario: The refusal of a task
- **WHEN** `is_placeholder` reads "Not yet: I need to inspect the repository first."
- **THEN** it is true

#### Scenario: A real text
- **WHEN** `is_placeholder` reads "The probe shows the path", "x-ray the cache" and "Draft the release notes"
- **THEN** it is false for each

### Requirement: A title shows a tag as text
`staging_title` and `delivery_title` SHALL keep each tag of the summary as it is, because a title is plain text. GitHub shows a tag word in a title as text, and the check `Semantic PR title` counts its characters. They SHALL still change the `<` of a comment opener into `&lt;`. They SHALL still put a handle or a link in a code span. The schema SHALL count the summary as the title shows it.

#### Scenario: A word in angle brackets in a title
- **WHEN** `staging_title` receives item 3 and the summary `Reject <section>.<option> keys`, and `delivery_title` receives `fix(config): reject <section>.<option> keys`
- **THEN** the titles are `docs(openspec): plan #3 Reject <section>.<option> keys` and `fix(config): reject <section>.<option> keys`

#### Scenario: A comment opener in a title
- **WHEN** `staging_title` receives item 3 and the summary `Block <!-- hidden`
- **THEN** the title is `docs(openspec): plan #3 Block &lt;!-- hidden`

#### Scenario: A summary of the most characters with a tag
- **WHEN** the model gives a summary of the most characters that the schema accepts, and the summary ends with ` <b>`
- **THEN** the schema accepts the reply, and the title passes the form check

### Requirement: The plan body passes the plan form before the draft opens
The stage job SHALL build the body of the draft pull request with `build_plan_body` and SHALL NOT write a body that `plan_body_problems` refuses. A refused body SHALL go back to the model with the other problems of the reply, and a refusal after the last return SHALL stop the item as a reply that fails its checks. A text with a closing keyword SHALL keep its own stop.

#### Scenario: The plan body passes
- **WHEN** the model gives a `pull_request_body` of 100 characters for issue 42
- **THEN** the draft pull request gets a body that `plan_body_problems` accepts

#### Scenario: A short body is returned once
- **WHEN** the first reply has a `pull_request_body` of 5 characters and the second reply has a text of 100 characters
- **THEN** the second request holds the problem of the short body, and the draft opens with the second body

#### Scenario: A second refusal stops the item
- **WHEN** the second reply and each later reply have a `pull_request_body` of 5 characters
- **THEN** the job stops the item, opens no draft pull request and pushes nothing

### Requirement: A security trigger needs a security section
The proposal check SHALL refuse a plan that names a security trigger and holds no non-blank `security` text, and SHALL name the matched path or word in the refusal. A trigger word SHALL match as a word, with an optional plural ending, and SHALL NOT match inside a longer word.

#### Scenario: A plan changes SECURITY.md with no security text
- **WHEN** `check_proposal` receives a proposal whose group changes `SECURITY.md` and whose `security` field is empty
- **THEN** it returns a problem that names `SECURITY.md` and asks for a non-blank `## Security` section

#### Scenario: A task names a trigger word with no security text
- **WHEN** `check_proposal` receives a proposal whose task text names `credential` and whose `security` field is empty
- **THEN** it returns a problem that names `credential`

#### Scenario: A plan with security text passes
- **WHEN** the same proposal holds non-blank `security` text
- **THEN** it returns no security problem

#### Scenario: A plan with no trigger needs no security text
- **WHEN** `check_proposal` receives a proposal whose Changes, group paths and task texts name no trigger
- **THEN** it returns no security problem

#### Scenario: A trigger word inside a longer word is no trigger
- **WHEN** `check_proposal` receives a proposal whose task text says "Add a regression test" and whose `security` field is empty
- **THEN** it returns no security problem

#### Scenario: A trigger word as a whole word is a trigger
- **WHEN** `check_proposal` receives a proposal whose task text says "Change the egress policy of the pod" and whose `security` field is empty
- **THEN** it returns a problem that names `egress`

### Requirement: The security triggers are a fixed list of paths and words
The trigger paths MUST be the named constant `SECURITY_TRIGGER_PATHS` with a docstring, and every entry MUST be a path of the repository.

#### Scenario: The trigger paths exist
- **WHEN** a test resolves each entry of `SECURITY_TRIGGER_PATHS` from the repository root
- **THEN** every entry is a file or a directory of the commit

#### Scenario: A trigger path is missing
- **WHEN** an entry of `SECURITY_TRIGGER_PATHS` names no file and no directory
- **THEN** the test fails

### Requirement: The design file holds the security section
`render_change` SHALL write a non-blank `security` field as a `## Security` section of `design.md`, and SHALL write no such section when the field is blank.

#### Scenario: A plan with security text is rendered
- **WHEN** `render_change` renders a proposal whose `security` field holds non-blank text
- **THEN** `design.md` holds a `## Security` section with that text

#### Scenario: A plan with no security text is rendered
- **WHEN** `render_change` renders a proposal whose `security` field is empty
- **THEN** `design.md` holds no `## Security` section

### Requirement: The stage prompt names the security rule
The stage prompt MUST name the `security` key, the `## Security` section and the security trigger.

#### Scenario: The prompt and the reply agree
- **WHEN** a test reads `roadmap_stage_change.md` and the fields of `StageProposal`
- **THEN** the prompt names `security` and the trigger, and the keys of the reply are the fields of the proposal

### Requirement: The stage prompt asks for a count of a claimed set
The stage prompt SHALL ask the plan to give a count of the set that a claim about every member covers, from the `references` tool or from a probe line, and it SHALL ask the proposal rule of `openspec/config.yaml` to hold the same phrase.

#### Scenario: A claim about a set
- **WHEN** the test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the prompt holds `gives a count from a tool of the plan run or from a probe line`

#### Scenario: No tool counts the set
- **WHEN** the test reads the stage prompt
- **THEN** the prompt holds `the count is unverified`, `census command` and `verify` of the first group

#### Scenario: A member has no decision
- **WHEN** the test reads the stage prompt
- **THEN** the prompt holds `removed, restricted, or allowlisted with a reason` and `a member with no decision`

#### Scenario: The count of a claim of no members is above zero
- **WHEN** the test reads the stage prompt
- **THEN** the prompt holds `narrows the claim` and `follow-up issue`

#### Scenario: The issue gives examples of a larger set
- **WHEN** the test reads the stage prompt
- **THEN** the prompt holds `the set that the issue names` and `not the set of its examples`

#### Scenario: The prompt and the config keep one phrase
- **WHEN** the test reads `openspec/config.yaml` and the stage prompt
- **THEN** both files hold `gives a count from a tool of the plan run or from a probe line`

### Requirement: The plan check refuses no word of a requirement text
The plan check SHALL NOT refuse a plan for the word `every`, `all` or `no` in a requirement text, so a claim about a set is judged by its count and never by a word.

#### Scenario: A requirement text holds every
- **WHEN** the test builds a plan whose requirement text holds `every` and whose paths exist at the staged commit
- **THEN** `check_proposal` returns no problem that names the word

### Requirement: A plan summary is no placeholder
The stage plan SHALL refuse a `summary` whose whole text is a placeholder word through `is_placeholder` of `src/devops_cli/roadmap/pull_form.py`. The refusal SHALL use the existing `stage_problem_text_placeholder` message with the field `summary`.

#### Scenario: A summary of one placeholder word
- **WHEN** A reply gives a `summary` of `x`.
- **THEN** The schema refuses the reply, and the problem names `summary`, the placeholder rule and the text `x`.

#### Scenario: A placeholder summary message
- **WHEN** A reply gives a `summary` of `todo`.
- **THEN** The error text is the rendered `stage_problem_text_placeholder` message for the field `summary` and the text `todo`.

#### Scenario: A real summary is accepted
- **WHEN** A reply gives a `summary` of `Refuse a placeholder plan summary`.
- **THEN** The schema returns no problem for `summary`.

### Requirement: A build cost states its time in minutes, hours, days or weeks
The stage job SHALL accept a time in `existing_tool` of a plan that sets `builds_own` to true when it is a number of minutes, hours, days or weeks, written with digits or with a number word from one to twelve, `a` or `an`. It SHALL still refuse a text that gives no count of tokens or no count of time.

#### Scenario: A time in days with a number word
- **WHEN** `builds_own` is true and `existing_tool` is `Cost: 80k tokens and about two days of elapsed time.`
- **THEN** `check_proposal` returns no cost problem.

#### Scenario: A time in weeks with digits
- **WHEN** `builds_own` is true and `existing_tool` is `Cost: 120k tokens, 1.5 weeks.`
- **THEN** `check_proposal` returns no cost problem.

#### Scenario: A time with no count
- **WHEN** `builds_own` is true and `existing_tool` is `Cost: 80k tokens and some days.`
- **THEN** `check_proposal` returns a problem that names the cost rule.

# pull-request-form Specification

## Purpose
The form of the title and the body of a pull request in this repository: the rules that CONTRIBUTING.md sets, held in one module; the command `devops pr describe`, which builds a title and a body in that form; and the check of `devops pr create`, which refuses a pull request that breaks it. Nothing in this capability cuts a text.

## Requirements

### Requirement: The title has a type, a declared scope and a short summary
A title SHALL have the form `<type>(<scope>): <summary>` or `<type>: <summary>`. The type SHALL be one of the types of the project. The scope, when there is one, SHALL be a scope whose `scope/<scope>` label `.github/labels.yml` declares, or `main`. The title SHALL have no `!`. The summary SHALL have at most 60 UTF-16 code units, as the check `Semantic PR title` counts them (an emoji is two), SHALL NOT end with `...` or `…`, and SHALL NOT be a placeholder such as `x` or `placeholder`.

#### Scenario: A title in the form
- **WHEN** the title is `feat(pr): check the form of a pull request` and the labels declare `scope/pr`
- **THEN** the rules find no problem

#### Scenario: A summary of 61 characters
- **WHEN** the summary of the title has 61 characters
- **THEN** the rules find one problem, and its text names the limit 60

#### Scenario: A scope with no label
- **WHEN** the title is `feat(zzz-unknown): build it` and the labels do not declare `scope/zzz-unknown`
- **THEN** the rules find one problem, and its text names `scope/zzz-unknown` and `.github/labels.yml`

#### Scenario: A cut summary
- **WHEN** the summary ends with `...`
- **THEN** the rules find one problem, and its text says that a cut summary reads as broken

#### Scenario: A placeholder summary
- **WHEN** the title is `feat(pr): x`
- **THEN** the rules find one problem, and its text says that the summary is a placeholder

#### Scenario: A mark of a breaking change
- **WHEN** the title is `feat(pr)!: build it`
- **THEN** the rules find one problem, and its text says that nothing is a breaking change before 1.0.0

#### Scenario: No scope check without the labels
- **WHEN** the rules check `feat(zzz-unknown): build it` and are given no label names
- **THEN** the rules find no problem

#### Scenario: An emoji counts as two
- **WHEN** the summary of the title is 31 emoji, which are 31 characters and 62 UTF-16 code units
- **THEN** the rules find one problem, and its text names the length 62 and the limit 60

### Requirement: The body ends with Closes and the Change line
The body of a delivery (a pull request whose title is no plan) SHALL be, in this order: a text of at least 20 characters (what the change does, and why), the line `Closes #<issue>`, the line `Change:` with the folder of the same issue in a code span, and then the attribution lines, if any. The text, `Closes` and `Change:` SHALL have at most 1,000 characters together, and the lines after them at most 400.

#### Scenario: A body in the form
- **WHEN** the body is a sentence, `Closes #3198` and a `Change:` line for issue 3198
- **THEN** the rules find no problem

#### Scenario: The folder of the change
- **WHEN** the `Change:` line names ``openspec/changes/3198-form/`` or ``openspec/changes/archive/2026-11-02-3198-form/``
- **THEN** the rules find no problem for either

#### Scenario: Attribution lines after the Change line
- **WHEN** the body in the form is followed by a `Co-Authored-By:` line
- **THEN** the rules find no problem, and those lines do not count toward the limit of 1,000 characters

#### Scenario: A missing Closes line
- **WHEN** the body has no line `Closes #<issue>`
- **THEN** the rules find one problem, and its text names the line

#### Scenario: A missing Change line
- **WHEN** the body has no line `Change:` in the form above
- **THEN** the rules find one problem, and its text names the line

#### Scenario: Two different issues in the two lines
- **WHEN** the `Closes` line names issue 3199 and the `Change:` line names issue 3198
- **THEN** the rules find one problem, and its text names both issues

#### Scenario: Closes after Change
- **WHEN** the line `Closes` comes after the line `Change:`
- **THEN** the rules find one problem, and its text says that `Closes` must come first

#### Scenario: A body over the limit
- **WHEN** the text, the `Closes` line and the `Change:` line have more than 1,000 characters
- **THEN** the rules find one problem, and its text names the length and the limit

### Requirement: The body closes one issue and holds no stand-in text
The body SHALL hold no closing reference other than its `Closes` line, no attribution line before `Closes`, no comment of the pull request template (`<!--`), no `BREAKING CHANGE`, and no placeholder as its text.

#### Scenario: Two issues
- **WHEN** the text says `fixes #12` and the body has the line `Closes #3198`
- **THEN** the rules find one problem, and its text says that the body closes 2 issues

#### Scenario: Attribution before Closes
- **WHEN** a `Co-Authored-By:` line is above the line `Closes`
- **THEN** the rules find one problem, and its text says to put attribution lines after the `Change:` line

#### Scenario: A placeholder or a short text
- **WHEN** the text above `Closes` is `x`, `placeholder` or fewer than 20 characters
- **THEN** the rules find one problem

#### Scenario: Template text
- **WHEN** the body keeps the comment of the pull request template
- **THEN** the rules find one problem, and its text says that the body keeps the comment of the template

#### Scenario: A breaking change footer
- **WHEN** the body holds `BREAKING CHANGE:`
- **THEN** the rules find one problem

### Requirement: The rules cut no text
The builders of the title and the body SHALL return the text as given, or raise `ValidationError` that names every problem. They SHALL NOT shorten a text, and no text they return ends with `...` because of a cut. The text they return SHALL pass the check of the same rules.

#### Scenario: A summary that is too long
- **WHEN** a title is built with a summary of 90 characters
- **THEN** the builder raises `ValidationError`, and its message names the limit 60
- **AND** it returns no title

#### Scenario: A why that is too long
- **WHEN** a body is built with a text that makes the body longer than 1,000 characters
- **THEN** the builder raises `ValidationError` whose message tells to shorten the text above `Closes`

#### Scenario: The body built passes the check
- **WHEN** a body is built from a text, an issue, a folder and two attribution paragraphs
- **THEN** the body is the text, `Closes #<issue>`, the `Change:` line and the two paragraphs, each after a blank line
- **AND** the check of the body finds no problem

### Requirement: devops pr describe prints the title and the body
`devops pr describe <issue> --summary <text>` SHALL print the title, a blank line and the body of the pull request that delivers the issue. The title SHALL have the type and the scope of the title of the issue, and `<text>` as its summary. The text of the body SHALL be `--why`, or else the section `Why` of the proposal in the change folder. The `Change:` line SHALL name the archive folder, with the date of today when the change is not archived. Each `--attribution` SHALL be a paragraph after it.

#### Scenario: A change that is not archived
- **WHEN** issue 1 is an item titled `feat(pr): build the form` and its change folder `openspec/changes/1-form/` has a section `Why`
- **THEN** the output is `feat(pr): <summary>`, a blank line, the why, `Closes #1`, and the `Change:` line with `openspec/changes/archive/<today>-1-form/`
- **AND** stderr names the date of today

#### Scenario: An archived change
- **WHEN** the change of issue 1 is in `openspec/changes/archive/2026-11-02-1-form/`
- **THEN** the `Change:` line names that folder, and stderr is empty

#### Scenario: The output passes the check of create
- **WHEN** `devops pr describe` prints a title and a body
- **THEN** the check of the title and the check of the body find no problem

#### Scenario: The why option
- **WHEN** `--why "A shorter reason, here."` is given
- **THEN** the body holds that text and not the section of the proposal

#### Scenario: Attribution paragraphs
- **WHEN** `--attribution` is given twice
- **THEN** the output ends with the `Change:` line, a blank line, the first value, a blank line and the second value

### Requirement: devops pr describe refuses and prints nothing
`devops pr describe` SHALL exit 1, print every problem to stderr, and print nothing to stdout when: the summary breaks a rule of the title; the scope of the issue has no label; the text makes the body longer than 1,000 characters; the proposal has no section `Why`; the text of the proposal holds a closing keyword for an issue; the issue has no change folder, or more than one; or the number is no item of the roadmap. It SHALL NOT cut a text.

#### Scenario: A summary of 61 characters or more
- **WHEN** the summary has more than 60 characters
- **THEN** the exit status is 1, stdout is empty, and stderr names the limit 60

#### Scenario: A placeholder summary
- **WHEN** the summary is `placeholder`
- **THEN** the exit status is 1 and stderr says that the summary is a placeholder

#### Scenario: A scope with no label
- **WHEN** the issue is titled `feat(zzz-unknown): a change` and the labels do not declare `scope/zzz-unknown`
- **THEN** the exit status is 1 and stderr names `scope/zzz-unknown`

#### Scenario: A why over the limit
- **WHEN** `--why` gives a text that makes the body longer than 1,000 characters
- **THEN** the exit status is 1, stdout is empty, and stderr tells to shorten the text above `Closes`

#### Scenario: A proposal with no why
- **WHEN** the proposal has no section `Why`
- **THEN** the exit status is 1 and stderr names the proposal and the option `--why`

#### Scenario: A why that closes an issue
- **WHEN** the section `Why` says `This closes #7`
- **THEN** the exit status is 1 and stderr names the closing keyword

#### Scenario: No change folder
- **WHEN** the issue has no folder under `openspec/changes/` and none in the archive
- **THEN** the exit status is 1 and stderr names the issue

#### Scenario: Not an item
- **WHEN** the number is no item of the roadmap
- **THEN** the exit status is 1 and stderr says that the issue is no item

### Requirement: devops pr create refuses a pull request that breaks the form
Before it sends the create request, `devops pr create` SHALL check `--title`, and `--body` in a repository with OpenSpec, with these rules. When there is a problem, it SHALL print every problem to stderr, exit 1, and open nothing, by `gh` or by the REST fallback. It SHALL check the scope against the labels file on the base branch and, without `--repo`, also against that of the checkout. A pull request that passes SHALL open as a draft, and the command SHALL have no option for another state.

#### Scenario: A title and a body in the form
- **WHEN** `devops pr create` is given a title and a body in the form
- **THEN** it sends the create request with `--draft`, and stderr is empty

#### Scenario: A title not in the form
- **WHEN** the title is `A plain title`
- **THEN** the exit status is 1, no create request is sent, and stderr says that the title is not in the form

#### Scenario: Every problem at once
- **WHEN** the title is `feat(zzz)!: ` followed by 61 characters and the body is empty
- **THEN** stderr names the `!`, the scope `zzz`, the limit 60, the missing `Closes` line and the missing `Change:` line

#### Scenario: A body that is not given
- **WHEN** `devops pr create` is given a title in the form and no body, in a repository with `openspec/config.yaml`
- **THEN** the exit status is 1 and no create request is sent

#### Scenario: The base branch declares fewer scopes
- **WHEN** the labels file on `--base` does not declare `scope/pr`
- **THEN** the exit status is 1, no create request is sent, and stderr names `scope/pr`

#### Scenario: A scope that only the checkout declares
- **WHEN** `--repo` is not given, the checkout declares `scope/newscope` and the base branch does not
- **THEN** a title with the scope `newscope` passes the check and the pull request opens

#### Scenario: A labels file that cannot be read
- **WHEN** the base branch has no `.github/labels.yml`
- **THEN** the exit status is 1, no create request is sent, and stderr names `.github/labels.yml`

#### Scenario: A refused pull request does not reach the fallback
- **WHEN** the title is `A plain title`
- **THEN** the REST fallback is not called

### Requirement: devops pr create checks the body only in a repository with OpenSpec
`devops pr create` SHALL check `--body` only where the base branch of the target repository (the default branch without `--base`) holds `openspec/config.yaml`. A read of the file that fails for another reason than a missing file SHALL stop the command with exit 1 and the error.

#### Scenario: A repository without OpenSpec
- **WHEN** the default branch of the repository that `--repo` names has no `openspec/config.yaml`, and the body has no `Closes` line and no `Change:` line
- **THEN** the command sends the create request with `--draft` and the body as given, and stderr is empty

#### Scenario: A repository with OpenSpec
- **WHEN** the default branch of the repository that `--repo` names holds `openspec/config.yaml`, and the body has no `Closes` line and no `Change:` line
- **THEN** the exit status is 1, no create request is sent, and stderr names the missing `Closes` line and the missing `Change:` line

#### Scenario: The base branch decides
- **WHEN** the default branch holds `openspec/config.yaml`, `--base legacy` names a branch without it, and the body has no `Closes` line
- **THEN** the command sends the create request

#### Scenario: A read of the switch that fails
- **WHEN** the read of `openspec/config.yaml` fails with an error that is not a missing file
- **THEN** the error is raised, and the command does not take the repository as one without OpenSpec

### Requirement: A dry run checks the form without a request
`devops --dry-run pr create` SHALL check the offline rules of the title and SHALL exit 1 with the problems when one fails. It SHALL check the body only when `--repo` is not given and the checkout holds `openspec/config.yaml`, because it cannot read the switch of another repository. It SHALL NOT read the labels file or `openspec/config.yaml` of GitHub, or open a roadmap store. `devops pr describe --dry-run` SHALL list the read of the issue and the read of the labels file, and SHALL read nothing.

#### Scenario: A dry run of a title not in the form
- **WHEN** `devops --dry-run pr create --title "A plain title"` runs
- **THEN** the exit status is 1, stderr says that the title is not in the form, and the command opened no roadmap store

#### Scenario: A dry run of a pull request in the form
- **WHEN** `devops --dry-run pr create` is given a title and a body in the form
- **THEN** the exit status is 0 and the output lists the requests of a real run, with the read of `.github/labels.yml`

#### Scenario: A dry run for another repository
- **WHEN** `devops --dry-run pr create --repo example/infra --head feat/19-x` is given a title in the form and a body with no `Closes` line
- **THEN** the exit status is 0, no `gh` command runs, no roadmap store opens, and the output names the branch `feat/19-x`

#### Scenario: A dry run of describe
- **WHEN** `devops pr describe 1 --summary "a summary" --dry-run` runs
- **THEN** the output lists a read of `repos/<repo>/issues/1` and a read of `.github/labels.yml`, and the command opened no roadmap store

### Requirement: The workflow and the module hold the same rule
The summary pattern and the scope list of `.github/workflows/pr-title.yml` SHALL allow the same titles as the rules: the pattern allows a summary of at most the limit of the module, and each scope of the workflow passes the check of the title.

#### Scenario: The pattern and the scopes
- **WHEN** a test reads `pr-title.yml` and `.github/labels.yml`
- **THEN** the pattern is `^.{1,60}$`, each scope of the workflow passes the check of the title, and a summary of 61 characters does not

### Requirement: A plan body has the Plans line and no closing keyword
`devops pr create` SHALL judge the body of a pull request whose title is `docs(openspec): plan #<issue> <summary>` by the form of a plan: exactly one line `Plans #<issue>` that names the issue of the title, no closing reference, and a `Change:` line with the active change folder of the same issue. The command SHALL NOT ask a plan body for a `Closes` line.

#### Scenario: A plan body in the form opens a draft
- **WHEN** the title is `docs(openspec): plan #3236 revise scope` and the body has the line `Plans #3236` and the line `Change: \`openspec/changes/3236-x/\``
- **THEN** the command opens a draft pull request.

#### Scenario: A plan body that closes its issue opens nothing
- **WHEN** the body of that plan has the lines `Plans #3236` and `Closes #3236`
- **THEN** the command prints that a plan closes no issue and opens nothing.

#### Scenario: A delivery title keeps the Closes rule
- **WHEN** the title is `feat(pr): check the form` and the body has no `Closes` line
- **THEN** the command prints that the body has no `Closes` line and opens nothing.

### Requirement: A title repeats no word and no issue number
When the summary of a title holds a word and an issue number (`<word> #<number>`), the rules SHALL give a problem if the first word after the number is that word, and a problem if the text after the number holds the same number. The word SHALL be the last word before the number. The comparison SHALL ignore case and the marks around the word. A later use of the word SHALL NOT be a problem.

#### Scenario: A repeated leading word
- **WHEN** the title is `docs(openspec): plan #2950 plan alternatives coverage telemetry`
- **THEN** the rules find one problem, and its text names the word `plan`

#### Scenario: A repeated issue number
- **WHEN** the title is `docs(openspec): plan #2950 Add coverage for #2950`
- **THEN** the rules find one problem, and its text names `#2950`

#### Scenario: A title with a new leading word
- **WHEN** the title is `docs(openspec): plan #2950 Add alternatives coverage telemetry`
- **THEN** the rules find no problem

#### Scenario: A later use of the word
- **WHEN** the title is `docs(openspec): plan #3200 Refuse placeholder and cut plan text`
- **THEN** the rules find no problem

#### Scenario: A repeat with a colon, a dash or a word before
- **WHEN** the title is `docs(openspec): plan #2950: plan x`, `docs(openspec): plan #2950 - plan x` or `docs(openspec): fix plan #2950 plan x`
- **THEN** the rules find one problem that names the word `plan`

#### Scenario: A number that only starts with the same digits
- **WHEN** the title is `docs(openspec): plan #2950 add #29501`
- **THEN** the rules find no problem

### Requirement: A plan body is built and checked in one module
`pull_form` SHALL build the body of a plan pull request with `build_plan_body`: the text, the line `Plans #<issue>`, the line `Change:` with the active change folder, in the order that `plan_body_problems` judges. The builder SHALL raise `ValidationError` with every problem when the body breaks the plan form, and SHALL NOT cut the text.

#### Scenario: A plan body in the form
- **WHEN** the builder gets a text of 100 characters, issue 42 and the folder `openspec/changes/42-x`
- **THEN** it returns a body that has the line `Plans #42` and the line ``Change: `openspec/changes/42-x/` ``, and `plan_body_problems` finds no problem

#### Scenario: A text that is a placeholder
- **WHEN** the builder gets the text `placeholder`
- **THEN** it raises `ValidationError`, and the message says that the body is a placeholder

#### Scenario: A text that closes an issue
- **WHEN** the builder gets a text that holds `Closes #7`
- **THEN** it raises `ValidationError`, and the message says that a plan closes no issue

### Requirement: devops pr create opens a pull request from the branch it is given
`devops pr create` SHALL take `--head` (`-H`), the branch that holds the commits of the pull request, and SHALL give it to `gh pr create` and to the REST fallback. Without `--head`, both SHALL use the branch of the checkout.

#### Scenario: A pull request in another repository
- **WHEN** `devops pr create --repo example/infra --head feat/19-x` runs in a checkout of another repository
- **THEN** the `gh pr create` command holds `--head feat/19-x` and `--repo example/infra`

#### Scenario: The REST fallback
- **WHEN** `gh pr create` fails, `--head feat/19-x` is given, and the checkout is on `main`
- **THEN** the fallback looks for an open pull request of `example:feat/19-x` and posts `head=feat/19-x`

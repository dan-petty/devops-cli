# roadmap-plan-check Specification

## Purpose
How `devops roadmap plan-check` judges a plan pull request: the change folder that it reads at the head of the pull request, the stage gates it runs with no model, the checks of the pull request itself, and how it reports each problem to a person and to an agent.

## Requirements

### Requirement: Plan-check reads the change folder at the pull request head
`devops roadmap plan-check <pull-request>` SHALL read the change folder of the pull request from its head commit.

#### Scenario: The head commit supplies the change folder
- **WHEN** the pull request head holds `openspec/changes/3201-plan-check/` and its base does not
- **THEN** the command reads `proposal.md`, `tasks.md` and each spec delta from the head commit.

#### Scenario: The change folder is found by the issue of the body
- **WHEN** the body holds `Plans #3201` and the head holds `openspec/changes/3201-plan-check/` and `openspec/changes/3199-other/`
- **THEN** the command reads `openspec/changes/3201-plan-check/` and no other folder.

#### Scenario: A missing or doubled change folder is a problem
- **WHEN** the head holds no change folder for the issue of the body
- **THEN** the command prints a problem that names the issue and exits 1.

### Requirement: The plan reader builds a StageProposal from a change folder
The plan reader SHALL build a `StageProposal` from the files of a change folder, with the same gate inputs as the proposal that `render_change` wrote. The estimate of the lines of a created file is no gate input, and the reader SHALL give each created path one line. The reader SHALL read the references of `## Unchanged references` of `design.md`.

#### Scenario: A rendered change reads back
- **WHEN** `render_change` writes a valid proposal with groups, specs and criteria
- **THEN** the reader gives a `StageProposal` whose `groups`, `specs`, `criteria` and `skip_specs` equal the original, with one estimated line for each created path.

#### Scenario: A created path reads back with one line
- **WHEN** `render_change` writes a group that creates `tests/test_sample.py` and estimates 40 lines
- **THEN** the reader gives that path in `creates` with an estimate of 1 line.

#### Scenario: A plan with inline verification reads back
- **WHEN** `tasks.md` names the kind of a group and holds `Verify that ... fails on the base` in the task text, as an older stage job wrote it
- **THEN** the reader gives the group its kind, its verification command and the task text without the verification phrase.

#### Scenario: A change folder with no criteria section reads back with no criterion
- **WHEN** `tasks.md` holds no `## Criteria` section
- **THEN** the `StageProposal` of the reader holds an empty `criteria` list.

#### Scenario: An unchanged reference reads back
- **WHEN** `render_change` writes a proposal with one unchanged reference
- **THEN** the reader gives that reference with its path, its kind and its reason

### Requirement: Plan-check runs the stage gates with no model
The command MUST run `check_proposal` and `validate_change` on the change folder of the pull request and MUST build no model client.

#### Scenario: The gates run with no model
- **WHEN** the command checks a valid plan
- **THEN** the test records a call to `check_proposal` and a call to `validate_change`, and no call that builds a model client.

### Requirement: Plan-check reports each stage problem
The command SHALL print each problem with its file, its rule and the message of the stage job, and SHALL exit 1 when it finds one.

#### Scenario: A missing path gives the stage message
- **WHEN** a group changes `src/devops_cli/roadmap/missing.py`, which the head tree does not hold
- **THEN** stdout holds the path and the missing-path message of `MESSAGES.roadmap`, and the exit code is 1.

#### Scenario: A valid plan prints no problem and exits 0
- **WHEN** the change folder passes `check_proposal` and `validate_change`
- **THEN** stdout holds no problem line and the exit code is 0.

### Requirement: Plan-check checks the title of the pull request
The command SHALL report a problem when the pull request title is not of the form `docs(openspec): plan #<issue> <summary>`, or when the text after the colon is longer than `SUMMARY_MAX_CHARS`.

#### Scenario: A wrong title is reported
- **WHEN** the pull request title is `feat(roadmap): add plan-check`
- **THEN** the output names the title rule and the exit code is 1.

#### Scenario: A title in the staging form passes
- **WHEN** the pull request title is the title that `staging_title` builds for the issue
- **THEN** the command reports no title problem.

### Requirement: Plan-check checks the body of the pull request
The command SHALL report a problem when the body is longer than `BODY_MAX_CHARS`, holds no `Plans #<issue>` reference, or holds a closing keyword before an issue reference.

#### Scenario: A missing plan reference is reported
- **WHEN** the pull request body holds no `Plans #` line
- **THEN** the output names the body rule and the exit code is 1.

#### Scenario: A closing keyword is reported
- **WHEN** the pull request body holds `Closes #3201`
- **THEN** the output names the closing keyword and the exit code is 1.

#### Scenario: A long body is reported
- **WHEN** the body is longer than `BODY_MAX_CHARS` characters
- **THEN** the output names the body length rule and the exit code is 1.

### Requirement: Plan-check reads the Semantic PR title check
The command MUST report the `Semantic PR title` check as a problem unless its conclusion is `success`.

#### Scenario: A failed check is reported
- **WHEN** the pull request has a `Semantic PR title` check with conclusion `failure`
- **THEN** the output names the check and the exit code is 1.

#### Scenario: A missing check is reported
- **WHEN** the pull request has no `Semantic PR title` check
- **THEN** the output names the missing check and the exit code is 1.

### Requirement: Plan-check reports a base spec that moved since the plan
The command SHALL report each `MODIFIED` requirement whose text in the base spec at the plan commit differs from its text at the pull request base.

#### Scenario: A changed base requirement is reported
- **WHEN** the base spec at the plan commit holds `The job SHALL stage one item.` and the base holds `The job SHALL stage two items.` for the same requirement
- **THEN** the output names the capability, the requirement and the moved text, and the exit code is 1.

#### Scenario: A removed base requirement is reported
- **WHEN** the base spec at the pull request base holds no requirement of that name
- **THEN** the output names the capability and the requirement and the exit code is 1.

### Requirement: Plan-check prints JSON
The `--json` option SHALL print the problems as a JSON array of objects with `path`, `rule` and `message`.

#### Scenario: JSON output parses
- **WHEN** the command finds one problem and runs with `--json`
- **THEN** stdout parses as a JSON array with one object that has `path`, `rule` and `message`.

### Requirement: Plan-check dry run makes no request
The `--dry-run` option MUST print each GitHub request and MUST make none.

#### Scenario: Dry run lists the requests
- **WHEN** the command runs with `--dry-run`
- **THEN** the output lists each request and the test records no GitHub API call.

### Requirement: Plan-check reports a file that it cannot read
The command SHALL report a problem that names the file when the plan reader cannot parse it, and SHALL go on to check the other files.

#### Scenario: An unreadable tasks file is reported
- **WHEN** the `tasks.md` of the change folder has a group with no `Changes:` line
- **THEN** the output names `tasks.md` and the exit code is 1.

### Requirement: The plan reader raises only a read error
The plan reader SHALL raise `PlanReadError` for each change folder that it cannot read, and SHALL NOT let a pydantic `ValidationError` leave `read_change`. The error of a task group SHALL name `tasks.md` and the title of the group.

#### Scenario: Each change folder of the tree
- **WHEN** a test runs `read_change` over each change folder of the tree
- **THEN** no error other than `PlanReadError` appears.

#### Scenario: A group that changes no file
- **WHEN** a group of `tasks.md` names no file in a code span after `Changes:`
- **THEN** `read_change` raises `PlanReadError` for `tasks.md` that names the group.

#### Scenario: A group that changes a path of the change folder
- **WHEN** a group changes `proposal.md` of the change folder
- **THEN** `read_change` raises `PlanReadError` for `tasks.md` that names the group.

### Requirement: The reader judges every verification command
The plan reader SHALL judge each code span of each `Verification:` line of a group with `verification_problem`, and SHALL raise `PlanReadError` for `tasks.md` that names each span that the implement step cannot run.

#### Scenario: A later task names a refused command
- **WHEN** the second task of a group names the verification `helm template loki`
- **THEN** `read_change` raises `PlanReadError` that names the command and the reason.

### Requirement: Plan-check reports a plan that the model refuses
The command SHALL report a `read` problem for a plan whose task group the model refuses, and SHALL exit with code 1 and print no traceback.

#### Scenario: A group with no changed file or a changed file in the change folder
- **WHEN** plan-check reads a plan with such a group
- **THEN** the output holds one problem with the path `tasks.md` and the rule `read`, the exit code is 1, and the output holds no traceback.

### Requirement: The plan reader keeps the document work of a group
The plan reader SHALL return the document work of a group from a documentation task that the renderer writes, with the verb that the renderer gives it.

#### Scenario: The document mark matches the new template
- **WHEN** the plan reader builds a proposal from a change folder whose group renders a documentation task that changes only `SECURITY.md`
- **THEN** the document work of the group is present in the built proposal and reads `Edit `SECURITY.md``.

### Requirement: Plan-check measures each task group
`devops roadmap plan-check` SHALL measure each task group of the plan with `measure_groups`, the function of the stage job, on the tracked files of the pull request head, with the body of the issue as the store reads it for the stage job, with no record block. The plan holds no estimate of the lines of a created file, so the measure SHALL count one estimated line for each created file.

#### Scenario: The figure equals the figure of the stage job
- **WHEN** a plan has a group that estimates one line for each file that it creates, and the budget is one token below the figure that `measure_groups` gives the stage job for that group
- **THEN** the `group-over-budget` problem holds that figure.

#### Scenario: The record block of the issue is not in the figure
- **WHEN** the body of the issue ends with the record block of the jobs, and the budget is one token below the figure that the stage job gives for the same text with no block
- **THEN** the `group-over-budget` problem holds the figure of the stage job, and a budget equal to that figure gives no problem.

### Requirement: Plan-check reports a group over the budget
The command SHALL read the budget from the setting `roadmap.stage.step_tokens`, and SHALL report a `group-over-budget` problem for each group whose figure is above it.

#### Scenario: A group over the budget is reported
- **WHEN** a group measures more tokens than `roadmap.stage.step_tokens`
- **THEN** the output holds a `group-over-budget` problem that names the group, its figure and the budget, and the exit code is 1.

#### Scenario: A group under the budget is not reported
- **WHEN** each group measures no more tokens than `roadmap.stage.step_tokens`
- **THEN** the output holds no `group-over-budget` problem.

### Requirement: Plan-check reports a group that packs no file
The command SHALL report a `group-no-files` problem for each group that changes a file that exists and packs no file. A group that only creates files SHALL be no problem. A path that an earlier group of the same plan creates SHALL count as present for a later group.

#### Scenario: A group that packs no file is reported
- **WHEN** a group changes a file of the pull request head and no code span of its tasks names a file of the head
- **THEN** the output holds a `group-no-files` problem that names the group, and the exit code is 1.

#### Scenario: A group that only creates files is not reported
- **WHEN** each path that a group changes is a path that it creates
- **THEN** the output holds no `group-no-files` problem for that group.

#### Scenario: A later group changes the file of an earlier group
- **WHEN** group 1 creates a file and group 2 changes that file and creates nothing
- **THEN** the output holds no `group-no-files` problem for group 2.

### Requirement: The plan reader reads the weakened checks of a plan
`read_change` SHALL read each bullet of the `## Weakened checks` section of `proposal.md` into `StageProposal.weakened_checks`, with the fields `check`, `stopped` and `safeguard`. The form of a bullet is `- **<check>**: Stopped: <stopped> Safeguard: <safeguard>`. The reader MUST raise `PlanReadError` that names `proposal.md` for a line of the section in another form.

#### Scenario: A section with two entries
- **WHEN** `proposal.md` holds two entries in the form
- **THEN** `read_change` gives both, each with its check, what it stopped and its safeguard

#### Scenario: A plan with no section
- **WHEN** `proposal.md` holds no `## Weakened checks` section
- **THEN** `read_change` gives an empty list

#### Scenario: An entry with no safeguard
- **WHEN** a bullet of the section holds no `Safeguard:` text
- **THEN** `read_change` raises `PlanReadError` for `proposal.md` that holds the bullet

### Requirement: The plan reader reports a criterion that the model refuses
The plan reader SHALL raise `PlanReadError` for `tasks.md` when `StageCriterion` refuses a criterion line, and the reason SHALL name the line and the problem. Plan-check and plan-recheck SHALL report it as a `read` problem and SHALL print no traceback.

#### Scenario: A criterion of group 0
- **WHEN** the criteria section of `tasks.md` holds the line `Group 0: The command prints one line for each problem`
- **THEN** `read_change` raises `PlanReadError` whose path is `tasks.md` and whose reason names the line.

#### Scenario: Plan-check reads a criterion of group 0
- **WHEN** plan-check reads a change folder whose `tasks.md` holds a criterion of group 0
- **THEN** the output holds one problem with the path `tasks.md` and the rule `read`, and the output holds no traceback.

#### Scenario: Plan-recheck reads a criterion of group 0
- **WHEN** plan-recheck reads a change folder whose `tasks.md` holds a criterion of group 0
- **THEN** the record of the folder holds a refusal of the gate `read`, and the run goes on.

#### Scenario: A criterion of group 1
- **WHEN** the criteria section of `tasks.md` holds the line `Group 1: The command prints one line for each problem`
- **THEN** `read_change` returns a criterion with the group 1.

### Requirement: The plan reader reads the dependencies of a plan
`read_change` SHALL fill `StageProposal.dependencies` with one entry for each bullet of the `## Dependencies` section of `proposal.md`, and MUST give an empty list when the section holds no bullet.

#### Scenario: Writer and reader round trip
- **WHEN** `render_change` writes a change whose `dependencies` list holds `#3201: the check command`, and `read_change` reads its `proposal.md`
- **THEN** `StageProposal.dependencies` holds `#3201: the check command`

#### Scenario: An empty section
- **WHEN** `render_change` writes a change whose `dependencies` list is empty, and `read_change` reads its `proposal.md`
- **THEN** `StageProposal.dependencies` is an empty list

### Requirement: The number reader takes only the issue form
`issue_dependencies` SHALL return the issue number of each `dependencies` entry that starts with `#<number>:`, and MUST skip every other entry.

#### Scenario: One issue entry and one overlap entry
- **WHEN** the dependencies hold `#3201: the check command` and `an open pull request changes src/devops_cli/roadmap/plan_check.py`
- **THEN** `issue_dependencies` returns `[3201]`

#### Scenario: An entry with no number
- **WHEN** the dependencies hold only `a metric name and its other files`
- **THEN** `issue_dependencies` returns an empty list

### Requirement: Plan-check reports an open issue dependency
`devops roadmap plan-check` SHALL report one problem with the rule `issue-dependency` for each issue dependency whose state is open, and MUST report no problem for an issue dependency whose state is not open.

#### Scenario: An open dependency
- **WHEN** the plan lists `#3224: the dependency record`, and the client answers that issue 3224 is open
- **THEN** the check reports one problem with the rule `issue-dependency` that names issue 3224

#### Scenario: A dependency that is not open
- **WHEN** the plan lists `#3224: the dependency record`, and the client answers that issue 3224 is not open
- **THEN** the check reports no problem for issue 3224

#### Scenario: An overlap entry
- **WHEN** the plan lists only the entry `an open pull request changes src/devops_cli/roadmap/plan_check.py`
- **THEN** the check reports no `issue-dependency` problem

### Requirement: Write, then read, keeps each fact of the files
For each valid proposal `p` whose texts hold no mark of the reader, `read_change(render_change(p))` SHALL equal `file_facts(p)`, and a read plan SHALL read back to itself. `FIELDS_NOT_IN_FILES` SHALL name the fields that no file holds: `summary`, `pull_request_body`, `builds_own`, `creates_lines` and `weakened_checks`. A changed reference is no fact of the files, because the writer writes only the unchanged references.

#### Scenario: A changed reference is no fact of the files
- **WHEN** `render_change` writes a proposal with one changed and one unchanged reference
- **THEN** the reader gives only the unchanged reference, and `file_facts` gives the same

#### Scenario: Each kind reads back
- **WHEN** `render_change` writes a proposal with one `behavior`, `manifest` or `other` group
- **THEN** the reader gives the group with the same kind

### Requirement: The plan reader reads the kind of each task group
The plan reader SHALL take the kind of a task group from its `Kind:` line when the word of the line is a kind. A group with no `Kind:` line, or with a word that is no kind, SHALL read as `behavior` when its first task fails on the base and it changes a path under `src/`, as `manifest` when its first task fails on the base and it changes no such path, and as `other` otherwise.

#### Scenario: A Kind line sets the kind
- **WHEN** a group says `Kind: other.` and its first task fails on the base
- **THEN** the reader gives the group the kind `other` with no test

#### Scenario: A word that is no kind
- **WHEN** a group says `Kind: documentation.` and its first task passes
- **THEN** the reader gives the group the kind `other`, as for a group with no `Kind:` line

#### Scenario: A plan head with no Kind line
- **WHEN** the reader reads the change folder of #4963 at 9c4b2cf75c64, whose group 3 changes only a dashboard and its test, with its case first
- **THEN** the reader gives group 3 the kind `manifest`, and groups 1 and 2 the kind `behavior`

### Requirement: The plan reader reads the RENAMED and REMOVED deltas
The plan reader SHALL read each FROM and TO pair of `## RENAMED Requirements` into `renamed`, and each requirement header of `## REMOVED Requirements` with its `**Reason**:` line and its optional `**Migration**:` line into `removed`. A FROM line with no TO line, a TO line with no FROM line, and a removal with no reason SHALL be a `PlanReadError` that names the spec file.

#### Scenario: A real RENAMED delta reads back
- **WHEN** the reader reads the spec delta of the archived change of #5150, which renames one requirement and modifies it under the new name
- **THEN** the spec holds the rename with both names, and the modified requirement under the new name

#### Scenario: A real REMOVED delta reads back
- **WHEN** the reader reads the spec delta of the archived change of #4798, which removes two requirements, each with a reason and a migration
- **THEN** the spec holds both removals with their names, reasons and migrations

#### Scenario: A FROM line with no TO line
- **WHEN** a RENAMED section holds a FROM line and no TO line after it
- **THEN** the reader raises `PlanReadError` that names the spec file

#### Scenario: A removal with no reason
- **WHEN** a REMOVED section holds a requirement header with no `**Reason**:` line
- **THEN** the reader raises `PlanReadError` that names the spec file

### Requirement: Plan-check compares a renamed requirement under its old name
The moved-spec check SHALL compare a MODIFIED requirement whose name is the `to_name` of a `renamed` entry with the base text under the `from_name`, at the plan commit and at the pull request base.

#### Scenario: A renamed and modified requirement with an unchanged base
- **WHEN** a plan renames a base requirement, modifies it under the new name, and the base spec does not change after the plan commit
- **THEN** plan-check reports no `spec-moved` problem

#### Scenario: The base text under the old name changed
- **WHEN** a plan renames and modifies a base requirement, and the base text under the old name changes after the plan commit
- **THEN** plan-check reports a `spec-moved` problem that names the old name

### Requirement: The stage job and the command share the rules of a plan
The rules of the title, the body, the plan reader, the stage gates and the size of each group SHALL have one code path in `src/devops_cli/roadmap/plan_check.py`, which `devops roadmap plan-check` and the stage job both call on a change folder in memory with the checkout that the measure reads (`PlanFolder`). The command SHALL read the folder from the detached worktree of the head of the pull request.

#### Scenario: The plan of #5407 before its push
- **WHEN** `staged_problems` judges the change folder of the head of #5407 on a clone that tracks each file that the plan names
- **THEN** it gives one problem: `group-no-files` for group 2 in `tasks.md`, with the message that the CI job `Plan Check` printed for #5407 word for word

### Requirement: The check before the push leaves out the rules of the pull request
`staged_problems` SHALL NOT judge the check `Semantic PR title`, a base spec that moved after the plan commit, or an open issue that the plan depends on. An open dependency holds the merge until it closes, and it is no fault of the plan.

#### Scenario: A plan that names an open issue
- **WHEN** `staged_problems` judges a plan whose `## Dependencies` names an issue
- **THEN** it gives no problem and reads no issue

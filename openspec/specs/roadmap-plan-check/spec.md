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
The plan reader SHALL build a `StageProposal` from the files of a change folder, with the same gate inputs as the proposal that `render_change` wrote. The estimate of the lines of a created file is no gate input, and the reader SHALL give each created path one line.

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

### Requirement: Plan-check judges a plan pull request
The command SHALL judge a pull request whose title is of the form `docs(openspec): plan #<issue> <summary>` or whose body holds the line `Plans #<issue>`, and it SHALL report no problem and exit 0 for a pull request that holds neither. The implement job writes the delivery title and the delivery body of the plan draft in one edit, so a run that starts before that edit reads a delivery pull request.

#### Scenario: A delivery pull request is not judged
- **WHEN** the pull request title is `fix(review): limit the lockfile bucket` and its body holds `Closes #3536` and no `Plans #` line
- **THEN** the command reports no problem and the exit code is 0.

#### Scenario: A body that plans an issue is judged whatever the title
- **WHEN** the pull request title is `feat(roadmap): add plan-check` and its body holds `Plans #3201`
- **THEN** the command judges the pull request and reports the title problem.

### Requirement: Plan-check checks the title of the pull request
The command SHALL report a problem when the title of a plan pull request that it judges is not of the form `docs(openspec): plan #<issue> <summary>`, or when the text after the colon is longer than `SUMMARY_MAX_CHARS`.

#### Scenario: A wrong title is reported
- **WHEN** the pull request title is `feat(roadmap): add plan-check`
- **THEN** the output names the title rule and the exit code is 1.

#### Scenario: A title in the staging form passes
- **WHEN** the pull request title is the title that `staging_title` builds for the issue
- **THEN** the command reports no title problem.

### Requirement: Plan-check checks the body of the pull request
The command SHALL report a problem when the body of a plan pull request that it judges is longer than `BODY_MAX_CHARS`, holds no `Plans #<issue>` reference, or holds a closing keyword before an issue reference.

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
The command SHALL report a `group-no-files` problem for each group that changes a file that exists and packs no file. A group that only creates files SHALL be no problem.

#### Scenario: A group that packs no file is reported
- **WHEN** a group changes a file of the pull request head and no code span of its tasks names a file of the head
- **THEN** the output holds a `group-no-files` problem that names the group, and the exit code is 1.

#### Scenario: A group that only creates files is not reported
- **WHEN** each path that a group changes is a path that it creates
- **THEN** the output holds no `group-no-files` problem for that group.

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

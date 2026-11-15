## ADDED Requirements

### Requirement: A refused body is rebuilt once
The job SHALL send every problem of a refused pull request body to the model one time, and SHALL rebuild the body from the reply. A rebuilt body that passes `body_problems` SHALL be written to the pull request. A rebuilt body that fails SHALL stop the item with the class `refused_reply`, and the job SHALL make no third model call.

#### Scenario: The first refusal
- **WHEN** `build_body` refuses the body that the job built
- **THEN** the job makes one model call that carries the refused text and every problem, and rebuilds the body from the reply

#### Scenario: The rebuilt body passes
- **WHEN** `body_problems` returns an empty problem list for the rebuilt body
- **THEN** the job writes the rebuilt body to the pull request and continues the step with no stop

#### Scenario: A second refusal
- **WHEN** `build_body` refuses the rebuilt body
- **THEN** the job stops the item with the class `refused_reply` and makes no third model call

## MODIFIED Requirements

### Requirement: The job rewrites the pull request after the push
Once the job has finished the change and before it pushes the commits, it SHALL set the title and the body of the pull request, with `build_body` for the body: the why of the `proposal.md`, `Closes #N`, and `Change:` with the change folder in a code span. It SHALL NOT cut the why. One pull request SHALL take one update, so a second call sends no `PATCH` and adds no label again. It SHALL post the outcome of each step as one comment after the push, and put nothing of it in the body.

#### Scenario: The body
- **WHEN** the job finishes the change of item 7
- **THEN** the body of the pull request starts with the why of the proposal, holds `Closes #7` before the `Change:` line, and ends with the `Change:` line of the archive folder, and `body_problems` finds no problem

#### Scenario: A project with no archive step
- **WHEN** the project declares no archive step, so the change folder stays active
- **THEN** the `Change:` line names `openspec/changes/<change>/`

#### Scenario: A long why is not cut
- **WHEN** the Why of the archived proposal is longer than the room that the 1,000 characters of the body leave
- **THEN** the body holds the title of the issue as its why, and holds no `...`

#### Scenario: A why that closes an issue
- **WHEN** the Why holds a closing keyword for an issue, or the proposal has no Why
- **THEN** the body holds the title of the issue as its why

#### Scenario: A refused body stops the item
- **WHEN** `build_body` refuses the rebuilt body too
- **THEN** the job stops the item at the step `pull request` with the class `refused_reply`, makes no `PATCH` of the pull request, makes no third model call, and the stop comment names the problems

#### Scenario: The metadata comes before the archived push
- **WHEN** a Staged item archives its change and a scoped check fails before the push
- **THEN** the `PATCH` of the title and the body came before the push of the archived commit, and the pull request holds the delivery title and a body that holds `Closes #1`

#### Scenario: One update for one pull request
- **WHEN** the run calls the metadata write twice for the same pull request
- **THEN** the job sends one `PATCH` and one label write, and the pull request holds each label once

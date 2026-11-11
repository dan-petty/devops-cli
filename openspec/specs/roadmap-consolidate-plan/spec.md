# roadmap-consolidate-plan Specification

## Purpose
The plan of the consolidation job of the roadmap: `devops roadmap consolidate` takes the shortlists of open items that may share a root cause, asks a model judge for a proposal and a refutation of each shortlist, checks the answers in code, and writes a local plan of proposed groups. A model verdict only flags a group. The command closes, drops, relabels and moves no item on GitHub.

## Requirements

### Requirement: The command joins the roadmap group
The `devops roadmap consolidate` command SHALL accept `--repo`/`-R`, `--ref`, `--limit`, `--dry-run`, `--confirm` and `--decline <group-id>`. Its help SHALL come from `RoadmapCommandHelp`, SHALL be a summary of at most three sentences, and SHALL name the page `docs/roadmap/consolidate.md`.

#### Scenario: The help names every option and its page
- **WHEN** a test reads `HELP.roadmap.consolidate` and the help of the command
- **THEN** the help names `docs/roadmap/consolidate.md`, the page exists, and every option above shows in the help of the command

### Requirement: A run writes a validated plan and no GitHub change
A run without `--decline` SHALL write no GitHub change. It SHALL write a Pydantic-validated plan to `.data/roadmap/consolidate/<date>.json` through `resolve_data_path`, and SHALL print a summary.

#### Scenario: The plan file is local and valid
- **WHEN** a test runs consolidate over an in-memory store with a scripted judge
- **THEN** the plan file exists at the resolved path and validates against the plan model, and the store holds no write

### Requirement: A group and a member hold their fields
Each group SHALL hold an id, a theme, a root cause, its members, its anchor, its shape, the consistency gained, the risks and a confidence. The shape SHALL be `merge-into-anchor`, `parent-task-with-children`, `close-as-duplicate` or `link-only`. Each member SHALL hold its action (`merge`, `child`, `link` or `close-when-anchor-merges`) and its evidence.

#### Scenario: Every group and member has its fields
- **WHEN** a test reads the plan of a scripted proposal
- **THEN** every group and member holds the fields above, with a shape and an action of the lists above

### Requirement: The plan is written after each shortlist
The run SHALL save the model output of each shortlist as soon as that shortlist is done, and SHALL write the final plan file only when every shortlist is done. A rerun over a shortlist with the same hash SHALL make no model call.

#### Scenario: A rerun makes no model call
- **WHEN** a test runs consolidate twice over the same board
- **THEN** the second run makes no judge call, and every group of its plan is marked as carried over from the earlier plan, so it proposes no new group

### Requirement: A dry run makes no request
`--dry-run` SHALL make no request and no model call, SHALL write no file, and SHALL return the plan type marked as a dry run with the requests a run makes.

#### Scenario: A dry run lists the requests
- **WHEN** a test runs consolidate with `--dry-run`
- **THEN** the output lists the reads and the model calls of a run, the store and the judge get no call, and no plan file exists

### Requirement: Two tool-less calls judge each shortlist
Each shortlist SHALL go through one function that takes the shortlist and its item texts and returns the verdict for each member. The model implementation SHALL make two tool-less `chat_structured` calls with the client of `ai.for_task("analysis")`: a proposal, then a refutation that sees the proposal and the member bodies and returns kept, weakened (link-only) or dropped, with reasons. Only a kept group SHALL have a non-link action. The change SHALL add no task key.

#### Scenario: The refutation decides the group
- **WHEN** a test scripts a proposal and a refutation of each of the three verdicts
- **THEN** a kept group keeps its actions, a weakened group has the shape `link-only` with every action `link`, a dropped group is not in the plan, and the second request holds the proposal and the member bodies

### Requirement: Code validates the proposal
Code SHALL drop a member or an anchor outside the shortlist, SHALL refuse a proposal with an unknown shape, and SHALL drop each cited `#N` that is no issue of the repository and each cited `path:line` that is no line of the file at the recorded commit.

#### Scenario: An invalid proposal is cut down
- **WHEN** a test scripts a proposal with a member outside the shortlist, a citation of an issue that does not exist and a citation of a line past the end of a file
- **THEN** the member and both citations are not in the plan, and the plan records each rejection
- **AND** a proposal with an unknown shape gives no group and records the failure with the class `parser`

### Requirement: A started item is never a member
An item with the status In Progress or In Review SHALL NOT be a member of a group. It SHALL be an anchor only for a group of the shape `link-only`.

#### Scenario: A started item is left out
- **WHEN** a shortlist holds an item with the status label In Progress as a member, and another as the anchor of a merge
- **THEN** the first is in no member list, and the group of the second has the shape `link-only`

### Requirement: A person-set milestone protects an item
An item with a milestone SHALL NOT get the action `merge`, `child` or `close-when-anchor-merges`, because no job writes a milestone, so a person set it. It MAY be an anchor, and MAY have the action `link`.

#### Scenario: A planned item is linked and not merged
- **WHEN** a scripted proposal merges an item with a milestone into the anchor
- **THEN** the plan gives that item the action `link`, and the other members keep their actions

### Requirement: A linked, declined or reopened group is not proposed again
A group whose members all link to its anchor already SHALL NOT be proposed. A member that a person reopened after a close as a duplicate of the anchor SHALL NOT be proposed for that anchor again. `--decline <group-id>` with `--confirm` SHALL write the decline in the job record of the anchor and nothing else, and SHALL keep the group out of the plan until its membership changes.

#### Scenario: Each rule keeps a group out
- **WHEN** a test runs consolidate over a board with a linked group, a group with a reopened member, and a declined group
- **THEN** none of the three is in the plan

#### Scenario: Decline writes only the job record
- **WHEN** a test declines a group of the last plan with `--confirm`
- **THEN** the job record of the anchor holds the group id, and the store holds no other write

#### Scenario: A change of members is a new group
- **WHEN** a group is declined and a new member joins its shortlist
- **THEN** the group has a new id and the plan proposes it

### Requirement: Close-when-anchor-merges stays in the plan
A member action `close-when-anchor-merges` SHALL stay in the plan as a pending close while its anchor is open, and SHALL leave it once its anchor is closed as completed.

#### Scenario: The pending close follows its anchor
- **WHEN** a test has such an action and an open anchor, and then closes the anchor as completed
- **THEN** the first plan lists the pending close and the next plan does not

### Requirement: An unreachable gateway fails closed
When the model gateway does not answer, the command SHALL write no plan file, SHALL exit non-zero, and SHALL name the gateway in its message.

#### Scenario: The gateway is down
- **WHEN** a test makes the scripted client raise an unreachable error
- **THEN** no plan file exists, the exit status is 1, and the output names the gateway

### Requirement: An unusable reply fails one shortlist
A shortlist whose reply the schema refuses SHALL be recorded in the plan with the failure class and the step name of `roadmap/failure.py`, and the run SHALL go on with the next shortlist.

#### Scenario: One shortlist fails
- **WHEN** a test scripts an unusable reply for one shortlist and a good reply for another
- **THEN** the plan holds the group of the second and a failure of the first with the class `parser` and the step `judge`

### Requirement: A reply cannot widen the plan
The plan SHALL hold only items of the shortlist that was judged, whatever the text of a member body asks.

#### Scenario: An injected body is not obeyed
- **WHEN** a member body tells the model to close #742, merge every issue into it and set P0, and the scripted model obeys
- **THEN** the plan holds only members of the shortlist and the store holds no write

### Requirement: The tests stay offline and fast
Each test of the command SHALL use the in-memory store, a fake embedder and a scripted `chat_structured` client, SHALL reach no network, model or cluster, and SHALL finish in one second.

#### Scenario: The tests reach no edge
- **WHEN** the new tests run
- **THEN** no network, model or cluster is reached, and each test finishes in one second

### Requirement: An MCP tool mirrors the plan run
The MCP tool `roadmap_consolidate` SHALL publish only `repo`, `ref`, `limit` and `dry_run`, SHALL set `readOnlyHint` to true, and its argv MUST NOT hold `--apply`, `--confirm` or `--decline`. No due-table row of the Service run SHALL start the job.

#### Scenario: A client calls the tool with every published option
- **WHEN** a client calls `roadmap_consolidate` with no option, and then with `repo`, `ref`, `limit` and `dry_run`
- **THEN** the argv of each call is `devops roadmap consolidate` with only those options, and it holds no write flag

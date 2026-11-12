# roadmap-stage/selection Specification

## Purpose
The Ready items that a stage round takes, the order in which it takes them, the items that it leaves out, and the settings and options that bound a round.

## Requirements

### Requirement: The label filter names the items to stage
`devops roadmap stage` SHALL take the open items whose labels match the `--filter family=value` options. The families are `status`, `priority`, `type`, `value` and `effort`. Values of one family SHALL be alternatives, and the families SHALL all apply. With no `--filter`, the filter SHALL be `status=ready`. A family that is not in the list SHALL be refused.

#### Scenario: The default filter
- **WHEN** the roadmap holds a Ready P1 bug, a Ready P3 feature, a Ready P2 docs item and a New P1 bug, and the command runs with no filter
- **THEN** the plan holds the three Ready items, and not the New one

#### Scenario: Values of one family
- **WHEN** the command runs with `--filter priority=p2-medium --filter priority=p3-low --filter status=ready`
- **THEN** the plan holds the Ready items of priority P2 and P3, and no item of another priority

#### Scenario: An unknown family
- **WHEN** the command runs with `--filter color=red`
- **THEN** the command exits 1, names the families it accepts, and makes no request

### Requirement: The job stages Ready items only
Whatever the filter says, the job SHALL stage an item only when its Status is Ready. A `status` filter can narrow the Ready items and SHALL NOT widen them.

#### Scenario: A filter with no status
- **WHEN** the roadmap holds a Ready bug, a New bug and a bug with no Status, and the command runs with `--filter type=bug`
- **THEN** the plan holds only the Ready bug, and it leaves out the other two and names their Status

### Requirement: The job leaves out the items it must not stage
The job SHALL leave out an item that is not Ready, has the label `needs-split`, fails the check of `roadmap-author-trust`, or depends on an open issue. It SHALL leave out a held item: `origin` or a worktree of the clone has a branch `<type>/<issue>-<slug>` for it. It SHALL leave out an item whose plan is on `origin/<default branch>` or whose change is archived there, matched by the issue number only. The plan SHALL name each item it leaves out and say why.

#### Scenario: Items that are left out
- **WHEN** the filter names a Blocked item, an item with `needs-split`, an item opened by an account with no write access that the jobs do not trust, an item of a bot that no review approved, an item that depends on an open issue, and an item with a pushed branch
- **THEN** the plan stages none of them and gives one reason for each

#### Scenario: The plan is on the default branch and the branch is gone
- **WHEN** `origin/main` holds the folder `openspec/changes/7-stop-the-drop/`, `origin` has no branch for item 7, the record of item 7 holds a `stage.pr` that is merged, and the title of item 7 gives another slug
- **THEN** the plan stages no item, and the reason for item 7 says that its plan is on `main` and names the folder

#### Scenario: The plan is on the default branch and the branch is still there
- **WHEN** `origin/main` holds the folder of item 7 and `origin` still has the staged branch of item 7
- **THEN** the plan stages no item, and item 7 has one reason

#### Scenario: The change is archived
- **WHEN** `origin/main` holds the folder `openspec/changes/archive/2026-10-28-7-stop-the-drop/`
- **THEN** the plan leaves out item 7 and the reason says that its change is archived on `main`

#### Scenario: The issue is closed
- **WHEN** the folder of item 7 is on `origin/main` and item 7 is closed
- **THEN** the plan holds no reason for item 7, because the job reads open items only

#### Scenario: A stale record and no plan on the default branch
- **WHEN** the record of item 7 names a merged `stage.pr` and a branch that is gone, and `origin/main` holds no folder for item 7
- **THEN** the plan stages item 7 again

#### Scenario: Two planned items
- **WHEN** `origin/main` holds the folders of items 7 and 8, and both are Ready bugs
- **THEN** the plan leaves out both, each with its own reason

### Requirement: A run stages a bounded number of items
`--limit`, default 3, SHALL cap the items a run stages. `--item N` SHALL stage the one item it names when that item is open and Ready.

#### Scenario: The limit
- **WHEN** the filter names five stageable items and the command runs with `--limit 2`
- **THEN** the plan holds the first two, by priority and then by number

#### Scenario: One item by number
- **WHEN** the command runs with `--item N` and #N is a Ready item
- **THEN** the plan holds #N alone, whatever the filter says

### Requirement: The settings name the filter, the limit and the step budget
The settings `roadmap.stage.filter`, `roadmap.stage.limit` and `roadmap.stage.step_tokens` SHALL set what the stage job takes. Each SHALL have the variable `DEVOPS_CLI_ROADMAP_STAGE_FILTER`, `DEVOPS_CLI_ROADMAP_STAGE_LIMIT` or `DEVOPS_CLI_ROADMAP_STAGE_STEP_TOKENS`. The defaults SHALL be the filter `status=ready`, the limit 3 and the step budget 64000, half of the default window of the implement task. The example ConfigMap of the Service SHALL hold the default filter.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a `roadmap.stage` setting
- **THEN** the filter, the limit and the step budget are the defaults above

#### Scenario: A config file and a variable
- **WHEN** the config file sets `roadmap.stage.limit` to 1 and the variable `DEVOPS_CLI_ROADMAP_STAGE_FILTER` holds `status=ready,type=feature`
- **THEN** the limit is 1 and the filter is `status=ready` and `type=feature`

#### Scenario: A round uses the settings
- **WHEN** the filter is `type=feature` and the limit is 1, and the roadmap holds two Ready features and a Ready bug
- **THEN** a round of the `stage` row plans the first feature only

#### Scenario: The example ConfigMap
- **WHEN** the example ConfigMap of the Service is rendered and loaded as settings
- **THEN** its stage filter equals the default filter

### Requirement: A filter entry is checked when the settings load
A filter entry SHALL be `family=value` over a label family of the stage job. The settings SHALL refuse any other entry and an empty filter, and the message SHALL name the entry.

#### Scenario: An invalid entry
- **WHEN** the filter holds the entry `color=red` or the entry `ready`
- **THEN** loading the settings fails with a message that names that entry

### Requirement: The options replace the settings for one run
`devops roadmap stage` SHALL use the filter and the limit of the settings when `--filter` and `--limit` are not given. The options SHALL replace them for that run.

#### Scenario: The options replace the settings
- **WHEN** the filter setting is `type=feature` and `devops roadmap stage --plan --filter status=ready --filter type=bug --limit 2` runs
- **THEN** the plan holds the Ready bugs, at most 2

### Requirement: The job leaves out an item that an agent or a person claimed
The job SHALL stage no Item that holds `owner/agent` or `owner/human`, `--item` included, and SHALL give the reason "It is claimed by agent." or "It is claimed by human.". An Item that holds `owner/service` SHALL not be left out for its owner.

#### Scenario: A claimed Item
- **WHEN** a Ready Item holds `owner/human` and the filter names it
- **THEN** the plan stages no Item and lists the Item as left out with a reason that contains "claimed by human"

#### Scenario: An agent claimed the named Item
- **WHEN** `--item` names a Ready Item that holds `owner/agent`
- **THEN** the plan lists the Item as left out with a reason that contains "claimed by agent"

#### Scenario: The Service holds the Item
- **WHEN** a Ready Item holds `owner/service`
- **THEN** the job stages it as it does an Item with no owner

### Requirement: The job takes the highest priority first
A run SHALL take the items that the filter names with the highest priority first, and the lowest issue number first among equal priorities. An item with no priority SHALL go last. The type of the branch of a staged item SHALL be the Conventional Commit type of its title.

#### Scenario: Priority order
- **WHEN** the default filter names a Ready P3 chore, a Ready P2 feature and a Ready P0 docs item, and the limit is 2
- **THEN** the plan stages the P0 docs item and the P2 feature

#### Scenario: The type of the branch
- **WHEN** the plan stages a feature titled `feat(cli): add a flag` and a docs item titled `docs(k8s): fix a path`
- **THEN** the branches start with `feat/` and `docs/`

### Requirement: The job leaves out a tracker
The job SHALL leave out an item that has sub-issues or the label `type/epic`, and the plan SHALL give the reason. Its sub-issues deliver it, so it gets no plan of its own.

#### Scenario: A tracker under the default filter
- **WHEN** the roadmap holds a Ready item with the label `type/epic`, a Ready item with two sub-issues and a Ready plain bug, and the command runs with no filter
- **THEN** the plan stages the plain bug only, and it names the tracker reason for the other two

### Requirement: The limit bounds a round, not the open drafts
`--limit` SHALL be the only bound on the staging drafts. The job SHALL NOT take fewer items because staging draft pull requests are open. A person merges or closes the plans.

#### Scenario: Drafts stay open
- **WHEN** three staging drafts are open and the roadmap holds more Ready items
- **THEN** the next round still stages up to `--limit` items

### Requirement: The plan lists the items that matched no filter when asked
`stage --plan` SHALL list, under "Matched no filter" and only with `--why`, each open item that the filter does not name. Each line SHALL name the family that the item misses, the values the filter takes, and the value the item has. The section SHALL not be part of "Left out". Without `--why`, the output SHALL not change.

#### Scenario: Why
- **WHEN** the filter is `priority=p0-critical` and a Ready P1 item exists
- **THEN** `stage --plan --why` lists the P1 item under "Matched no filter" with the family `priority`

#### Scenario: No why
- **WHEN** the same plan runs without `--why`
- **THEN** the output has no section "Matched no filter"

### Requirement: A setting names the limit on Planned items
The setting `roadmap.stage.planned_limit` SHALL be the count of open Planned items at which the stage job plans only items with the priority `P0-Critical` or `P1-High`. It SHALL have the variable `DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT`, the default 20 and a least value of 1. The example ConfigMap of the Service SHALL hold the default.

#### Scenario: The default
- **WHEN** no config file and no variable sets `roadmap.stage.planned_limit`
- **THEN** the limit is 20

#### Scenario: A config file and a variable
- **WHEN** the config file sets `roadmap.stage.planned_limit` to 7 and then the variable `DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT` holds 9
- **THEN** the limit is 7 from the file and 9 with the variable

#### Scenario: A limit under 1
- **WHEN** the config file sets `roadmap.stage.planned_limit` to 0
- **THEN** loading the settings fails

### Requirement: The stage job plans only P0 and P1 items at the limit on Planned items
When the count of open Planned items is at `roadmap.stage.planned_limit` or over it, the stage job SHALL take only an item with the priority `P0-Critical` or `P1-High`. It SHALL leave out each other item that passes every other rule, with a reason that names the count, the setting and the two priorities. The item that `--item` names SHALL pass the limit. The count SHALL hold open items with the Status Planned only. The limit SHALL NOT apply to the filing of issues.

#### Scenario: At the limit
- **WHEN** 2 items are Planned, the limit is 2, and a Ready `P2-Medium` item passes every other rule
- **THEN** the job takes no item, and the reason of the Ready item names the count 2, the setting `roadmap.stage.planned_limit` and `P0-Critical or P1-High`

#### Scenario: Under the limit
- **WHEN** 1 item is Planned, the limit is 2, and two Ready items pass every other rule
- **THEN** the job takes both items

#### Scenario: An item of the highest priority
- **WHEN** 2 items are Planned, the limit is 2, and a Ready `P0-Critical` item and a Ready `P2-Medium` item pass every other rule
- **THEN** the job takes the `P0-Critical` item and leaves out the `P2-Medium` item with the reason of the limit

#### Scenario: The priorities that pass
- **WHEN** 2 items are Planned, the limit is 2, and a Ready `P0-Critical` item, a Ready `P1-High` item, a Ready `P2-Medium` item and a Ready `P3-Low` item pass every other rule
- **THEN** the job takes the `P0-Critical` item and the `P1-High` item, and leaves out the other two with the reason of the limit

#### Scenario: A closed item and an item of another Status
- **WHEN** 1 open item is Planned, 1 closed item is Planned, 1 item is Staged, and the limit is 2
- **THEN** the count is 1 and the job takes a Ready item

#### Scenario: A named item
- **WHEN** 2 items are Planned, the limit is 2, and `--item` names a Ready `P2-Medium` item
- **THEN** the job takes that item

#### Scenario: Another rule fails first
- **WHEN** 2 items are Planned, the limit is 2, and a Ready `P2-Medium` item is claimed by a person
- **THEN** the reason of that item is the claim, not the limit

#### Scenario: The command at the limit
- **WHEN** 1 item is Planned, the setting is 1, and `devops roadmap stage --plan` runs with a Ready `P2-Medium` item
- **THEN** the plan holds no branch, makes no model call, and lists the Ready item as left out with the reason of the limit

### Requirement: A failed item waits for the retry delay
The job SHALL leave an item out of the selection until the `RETRY_AFTER` wait of the class in `stage.failed_class` has passed since `stage.failed_at`, and SHALL take the other items in the same round. A missing or unknown class SHALL wait as `ci_infra`. `--item` SHALL take the item it names. A failure time that is no time SHALL hold the item for no time. No setting SHALL change the wait, and the job SHALL NOT store the time it waits until.

#### Scenario: The delay has not passed
- **WHEN** the item failed 59 minutes ago with the class `provider`
- **THEN** the job leaves the item out and takes the next item

#### Scenario: The delay has passed
- **WHEN** the item failed 1 hour ago with the class `provider`
- **THEN** the job takes the item again

#### Scenario: A refused plan waits longer
- **WHEN** the item failed 59 minutes ago with the class `plan_defect`
- **THEN** the job leaves the item out, and takes it again 1 hour after the failure

#### Scenario: A reply that breaks the schema waits six hours
- **WHEN** the item failed 1 hour ago with the class `parser`
- **THEN** the job leaves the item out, and takes it again 6 hours after the failure

#### Scenario: An item that changed does not wait
- **WHEN** the item failed with the class `head_moved`
- **THEN** the job takes the item in the next round

#### Scenario: A record with no class
- **WHEN** the job record holds `stage.failed_at` of 59 minutes ago and no `stage.failed_class`
- **THEN** the job leaves the item out, and takes it 1 hour after the failure

#### Scenario: A class that is unknown
- **WHEN** the job record holds a `stage.failed_class` that is no failure class
- **THEN** the item waits as `ci_infra` and the selection does not fail

#### Scenario: A person names the item
- **WHEN** the item failed 1 minute ago and a run names it with `--item`
- **THEN** the job takes the item

#### Scenario: A stale setting
- **WHEN** a config file still holds `roadmap.stage.retry_hours`
- **THEN** the settings load without error and the stage settings hold no such field

### Requirement: The stage selection leaves out an item with an open recorded blocker
The stage selection SHALL leave out an item whose `refine.blocked_by` record names an open item. The reason SHALL name each open item.

#### Scenario: The recorded blocker is open
- **WHEN** an item's job record holds `refine.blocked_by` with #3308, and #3308 is open
- **THEN** the stage selection leaves out the item, and the reason names #3308

#### Scenario: The recorded blocker is closed
- **WHEN** an item's job record holds `refine.blocked_by` with #3308, and #3308 is closed
- **THEN** the stage selection does not leave out the item for that record

### Requirement: A left-out item counts and logs its reason
A stage round SHALL count a skipped item in `devops_cli_roadmap_stage_total` with the label `reason`, a bounded kind of the rule that left it out, such as `title_type`, `held`, `returned` or `rejected`, and `none` for another result. The Service SHALL log the kind and the text of the reason of a left-out item once, and again only when its kind changes.

#### Scenario: Each result carries a reason label
- **WHEN** a round leaves one item out for its title type, stages one, returns one and finds one rejected
- **THEN** the counter has one point each for `title_type`, `returned` and `rejected` under `skipped`, and one for `none` under `staged`

#### Scenario: A reason logs once until it changes
- **WHEN** three rounds leave one item out, the first two for its title type and the third for the label `needs-split`
- **THEN** each round counts the item, and two log lines name the item, one with `title_type` and one with `needs_split`

### Requirement: The stage job reads a dependency named by its title
The stage job SHALL leave out an item whose Dependencies section names an open issue by its quoted Conventional Commit title, as it does for `#N`. A title SHALL name the one open Item with that exact title, else the one closed Item with it. A closed issue SHALL hold nothing back.

#### Scenario: An open and a closed issue named by their titles
- **WHEN** one Ready item names an open issue and a closed issue by their quoted titles, and another Ready item names only the closed issue
- **THEN** the job leaves out the first item with the reason that names the open issue, and it stages the second item

# Design

## Decisions

- **One pure function derives the Status.** `derive_status(facts)` takes `StatusFacts` (the plan is merged, a Job holds the item, the delivery pull request is ready, the item is blocked) and returns one Status. The order is Blocked, In Progress, In Review, then Planned or Ready. The rows read the facts in different ways: `implement` and `stage` from the tree of the default branch, `stage_ready` from the merge of the plan pull request. The decision is the same for all of them.
- **The "plan is merged" fact is the tree of the default branch.** `Ready until the plan pull request merges` is the same as "the change folder of the item is on `origin/<default>`", which is what the implement job calls a Planned item. An archived folder counts too. `stage_ready` has no clone, so for it the fact is `merged` of the stage pull request.
- **The Service writes only from Ready or Planned.** The sources of a write are the two Statuses that the Service itself owns. A write to In Progress, In Review or Blocked starts from them. The Service never leaves In Progress, In Review, Blocked or New. This keeps the manual flow whole: `devops pr create` sets In Progress for a pull request that a person or an agent opens, and the Service must not turn it back to Planned. A Job that ends and leaves its item In Progress is still reported and set back by the code that exists (`_report`).
- **The label must be what a job last wrote.** The Service writes only when `item.status` equals the Status in the job record. This is how it tells its own labels from a person's change that came before the read. The race after the read stays with `set_field`, which raises `RoadmapItemChangedError` (ADR 0016). A person who moves a label keeps it, until a job writes the field again.
- **The family replace of the store does the write.** `set_field` removes each `status/*` label and adds the new one in one `PATCH`. No new label code.
- **Failures are per item.** `sync_statuses` runs each item through `write_each` of the stage job, so one failed item does not stop the others. The row reports the failures after its own work: the row `implement` still submits its Job when a status write failed.
- **The implement row reads the plans once.** `plan_implement` takes the `PlannedChanges` that the round already read, so the sweep and the plan share one `git fetch` and one `git ls-tree`. The sweep runs before the wait on a running Job, so a Job that runs for an hour does not freeze the labels.
- **The stage row shares the plans of its plan.** `StagePlan` carries the `PlannedChanges` that `plan_stage` read, so the sweep after `apply_stage` adds no git command.
- **The pull request of a delivery is read rarely.** Only an item with `implement.pr`, no stop, no open Job and the Status Ready or Planned is read. A Job that finishes sets In Review itself, so such an item is a Job that died after it marked the pull request ready.
- **Blocked is a fact, not a path.** `StatusFacts.blocked` is part of the function and has a test. No caller sets it, because the stop path and the retry comment are the work of a later issue. Until then a stop leaves the item Ready, and the next sweep makes it Planned when the plan is merged.
- **The plan of the implement job accepts the Statuses it can meet.** Ready and Planned are the items to implement. In Progress with a recorded Job that no round reported is the item whose Job is the process that runs the plan. The default filter names `status=ready` and `status=planned`, so a Planned item is in the list. `--item` skips the filter and keeps the check.

## Rejected alternatives

- **A new store method for the Status.** `set_field` already replaces a family, records the value and refuses a changed field. A second method would copy the rule of the person's change.
- **Let the runner Job set every Status.** The Job exists only while it runs. A Planned item has no Job, and a drift after a crash has none to repair it. The Service runs every round.
- **Move the Service's write to In Progress only when the Job starts.** The Service would show a Planned label between the creation of the Job and its first write, and the sweep would have to guess a Job that is waiting for a node. The record names the Job at once.
- **Repair a Status that a person set when the facts say otherwise.** The ADR forbids a revert of a person's change. A person who moves a label back to Ready is not corrected.
- **Derive the Status for every item from the facts, with no source rule.** It would turn a manual In Progress into Planned in the next round. The claim labels of a later issue are the right way to mark a manual claim.
- **Read the plan pull request for every item in `implement`.** One `git ls-tree` gives every plan for the price of one command. A pull request read costs one request for each item.
- **A cache of the Status in a new record key.** The label is the Status and the record already holds the value that a job wrote under the key `Status`.

# Design

## Decisions

- **Only `plan_defect` counts.** A refused plan is the loop of #4491. A `provider`, `parser`, `ci_infra` or `head_moved` failure keeps its `RETRY_AFTER` wait and leaves the count as it is.
- **The count keys on the body.** `stage.plan_defects_body` holds `hash_text(without_alternatives(body))`: the text of a person and the refine section, without the block of the alternatives job, as `body_hashes` leaves it out. An edit of a person, or a new design of refine, starts a new count.
- **The limit is 3** (`CONST_ROADMAP_STAGE_PLAN_DEFECT_LIMIT`). In the 48-hour window, 5 of the 6 staged plans came after 2 refused plans, so a limit of 2 would return most items that stage. 27 items failed more than 2 times.
- **The return is in the failure write.** `_record_failures` returns the item at the limit in the same round, in place of the write of the count. The record never holds a count at the limit, so the selection needs no new check: the item is New, and `_not_ready` leaves it out.
- **The return goes through refine.** The return sets New with the failure marks and no count, and it changes no refine key. Refine looks at the item once more and reads the comment (#3483). After a second return on the same body, refine waits for a reply or a body edit. A person who sets the item Ready again starts at a count of zero.
- **The evidence comes from the planner.** `StageFailure.problems` holds the problem of each reply that the checks refused in the plan, masked and cut to `CONST_ROADMAP_STAGE_REFUSED_PROBLEM_MAX_CHARS`, as `RefusedRecord.of` keeps them. The comment lists these problems in sequence and then the reason of the failure, unless the checks refused the last reply (`StageFailure.stopped_by_checks`): a plan run that stops after a refused reply must show why it stopped. `safe_text` puts each problem on one line, so it pings no one.
- **The comment goes first.** As in `_stop_on_budget`, a failed status write never leaves a return that no one was told about. A failed write ends the run, as each write of `_record_failures` does.

## Rejected alternatives

- **The gate version or the prompt version in the key of the count.** 8 releases in 48 hours changed a gate file of `STAGE_EVAL_TRIGGER_PATHS` or a stage prompt. Replayed on the window, a key with the gate version lets no item reach the limit, and a key with the prompt version lets 2 of 10 items reach it. Refine's look after the return and a reply of a person give an item a new try after a gate fix.
- **A back-off that doubles on a repeated problem set** (study R22, #4131, #4060). #4491 asks for a limit. The study ranks R22 as "later, or only with more data". Only 19 of 38 pairs of consecutive refusals of one item repeat the same class of problem, and a problem names no gate, so a signature of the problem set needs a change of the gates.
- **Hold the item Ready and leave it out.** The item then waits with no job that acts on it, and AGENTS.md rule 2 returns an item that cannot be built as written to New with the evidence.
- **A check in the selection that returns an item at the limit.** It needs a new list in `StagePlan`, a write in `StageWriter.begin` and a line in the report, and it returns the item one round later. The return in the failure write needs none of them.
- **Read `<n>.refused.json` for the evidence.** The planner holds the same problems in memory, and a run with no plan files writes no file.
- **Count every failure class.** A provider outage or a parser error is no refused plan and has its own wait.

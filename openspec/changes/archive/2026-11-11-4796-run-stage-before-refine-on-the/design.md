# Design

## Decisions

- **Stage before refine, for every round.** The rows of a lane run in the order of the table. Stage moves before refine, and the order needs no condition on the count of Ready items: with no Ready item, the stage round selects nothing and calls no model, so refine still gets almost all of the lane.
- **Refine is the right row to cut.** A restart stops the round in flight. Refine writes each item when it is done (#3631), so it loses at most one item of about 6 minutes. A stage item takes about 21 minutes at p50. With stage first, the first round of a new pod gives stage its turn, and the restart cuts refine at the end of the pod instead.
- **The `stage_due` stamp keeps #2659.** Stage now runs before refine in a round, so the cross-job rule that read refine's outcome in the same round can never fire. The round writes `stage_due` at the time of the round when a row's outcome set an item Ready, also when that row failed. Stage is due when the stamp is at or after its last success: stage ran before refine in that round, so a stamp equal to the last success of stage still names an item that became Ready after stage ran. Intake's `refine_due` keeps the strict comparison, because intake runs before refine.
- **Retitle stays just before stage.** The stage job reads the new titles in the same round.

## Rejected alternatives

- **A time bound on a refine round** (for example, take no new item after 17 minutes). The lane model gives stage 0.87 to 1.15 rounds an hour and refine 3.0 to 4.6 items an hour. With no restart, refine falls to 3.0 to 3.9 items an hour, where the order alone keeps 4.6 to 5.6. It breaks the limit of 7 items that #4426 asked for, and it does not help the first round of a new pod.
- **Round robin with the start time of each row in `schedule.json`.** The lane model gives stage 0.82 to 0.95 rounds an hour and refine 4.6 to 5.4 items an hour. It needs a new record of each row's last start, and it still lets refine run first after a restart when stage ran last before it. Stage is the row that limits the plan pull requests (149 Ready items, 0 Planned), so the simpler order that favours stage is the better trade.
- **Stage in its own lane in the Service.** It needs a fourth worker, a fourth clone and a cross-lane stamp, and the model slot (`service.model_call_concurrency` 1) is shared by all lanes, so both rows slow down. #4559 moves stage into its own Job, which is the full fix.
- **Lower refine's limit or interval.** It reverts the owner's decision in #4426.

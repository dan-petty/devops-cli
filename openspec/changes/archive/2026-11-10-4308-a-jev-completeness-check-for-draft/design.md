# Design

## Decisions

- **One request for each decision.** All questions go in one `DecisionRequest`: one Noul question for each criterion (`criterion_<n>`) and one Score question (`tests`) with a rubric of four levels. The criteria and the diff are in the state, and each criterion is also in its question, so a question reads alone.
- **A hold, never a pass.** The result `held` or `error` keeps the draft a draft. A `passed` result changes nothing: the checks and a person still decide. The check never marks a pull request ready, merges or closes, and a test shows that a failed check stops it before Jev is asked.
- **Fail closed, with a retry.** An error of Jev (`AgentRunError`, `UserError`) holds the draft, is logged and counted, and posts one note for the head commit. The next round asks again, so a transient error does not hold the draft for good. A hold by doubt is recorded as `stage.jev = <sha>:held` and is not asked again for that head commit; a new commit is checked again.
- **Thresholds in the constants module.** `CONST_ROADMAP_JEV_CRITERION_THRESHOLD` (0.50, the default boolean threshold of Jev), `CONST_ROADMAP_JEV_MIN_TEST_SCORE` (1.0 of 3), `CONST_ROADMAP_JEV_MAX_DIFF_TOKENS` (one fourth of the window of Jev, counted with the shared `count_tokens`) and `CONST_ROADMAP_JEV_MAX_CRITERIA` (40). The thresholds were fixed before the run of the set; the report sweeps other values without a new request.
- **Only the stage row.** The Service marks stage drafts ready in `stage_ready`. The implement job marks its own draft inside a runner Job, and a hold there would stop the item. A follow-up decides it after the set shows that the check works.
- **Default off.** The set decides: the switch stays off while the false holds exceed 10% or the set is too small (`CONST_ROADMAP_JEV_EVAL_*`). A person turns it on.
- **A new model for each request.** See Feasibility.
- **The set is paired.** Each removed-hunk case has a complete twin with the same diff, so the effect of the one hunk is measured with no other change. The incomplete plans come from the `criterion_dropped` defects of the stage golden set.

## Rejected alternatives

- **A threshold tuned on the set.** The number of cases is too small to hold out a test part, and a tuned value would hide the false holds. The report shows the sweep, and the configured value stays 0.50.
- **A free-text review by a chat model.** It costs more by two orders of magnitude, gives no calibrated probability, and the owner direction of 2026-10-03 says that a model alone originates no blocking finding. Jev gives a number and the check only holds.
- **Marking a draft ready on a pass.** A pass of a model must not outweigh the checks or a person.

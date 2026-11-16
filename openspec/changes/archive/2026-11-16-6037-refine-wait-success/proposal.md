# Proposal: #6037

## Why
The success set of refine (`SUCCESS_RESULTS[RoadmapJob.REFINE]`) holds `ready`, `person`, `split` and `blocked`. A refine attempt that sets the next step `alternatives` logs `success=false`. But `alternatives` is a wait like `blocked`: a ready proposal waits on the verdict of the alternatives row (#2951). So the grade of refine is too low. In the 24 hours to 2026-11-16 20:45Z, refine logged ready 41, blocked 30, person 28, alternatives 14, split 2 and retry 5. The grade showed 101/120, but only the 5 `retry` results are failures of the job (115/120). Nothing stops the next new value of `NextStep` from the same error.

Closes #6037.

## What Changes
- The success set of refine holds each value of `NextStep` that is a wait: `ready`, `person`, `split`, `blocked`, `alternatives` and `edit`. `retry` and `failed` stay failures, and `none` writes no line.
- A test compares the success set with the values of `NextStep` less `retry`, `failed` and `none`. A new value of `NextStep` makes the test fail until the set holds it, or until the test names it as no wait.
- The first-pass rule of refine (`tries` = 1) needs no change. `is_first_pass` reads the success set, so an `alternatives` line of the first try is a first pass.
- `docs/roadmap/job-success.md` gives the new intended result of refine.

## Capabilities
- `roadmap-job-grades`: 1 added requirement.

## Impact
- The `success` and `first_pass` fields of the refine lines change for `alternatives` and `edit`. The dashboard row `Roadmap Job Success` and `devops roadmap eval grades` count the field, so their ratio of refine goes up. The older lines in Loki keep `success=false`.
- No command, setting or manifest changes. The change fits one pull request.

## Feasibility
- `src/devops_cli/roadmap/refine/refine.py`: `_log_attempt` logs the value of the next step as the result, and `error` for a failed model call or write.
- Loki, 7 days to 2026-11-16: the refine lines hold `ready` 136, `person` 114, `blocked` 112, `alternatives` 26, `split` 13, `retry` 23, `failed` 5 and `error` 43, and no `edit`.
- The new tests fail on the base: `alternatives` logs `success=false first_pass=false`, and the set holds neither `alternatives` nor `edit`.

## Existing Tool Considered
None applies: the set is a table of the project. The change adds 2 values and a test. Cost: about 40k tokens and 30 minutes.

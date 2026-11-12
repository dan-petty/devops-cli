# Proposal: #4479

## Why

The citation gate of the stage plan check refuses a `path:N:text` citation when line `N` of the staged file does not hold `text`. Most of these citations are stale and not false: the planner copies a line number from another commit, and the text is still in the file at another line. The study of the stage refusals of 2026-11-11 counted 41 stale citations, and in 33 of them the text is on exactly one line of the staged file. Each such refusal costs one more reply, and the second reply often fails again. Closes #4479.

## What Changes

- `_plan_citation_problems` in `src/devops_cli/roadmap/stage/stage_change.py` accepts a `path:N:text` citation whose text is not on line `N` when exactly one other line of the staged file holds the text. It compares each line as it compares line `N`: the cited text after white space collapses is in the line after white space collapses. A line `N` past the end of the file is a stale line number too.
- The gate refuses the citation, as before, when no line or more than one other line holds the text. The minimum of 3 characters applies before the gate looks at other lines, and a citation whose line `N` holds the text is not re-anchored.
- A check with a reader of the staged files writes one log line, `The citation gate re-anchored <n> of <m> line citations.`, so the job log shows the rate.
- The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`, its prompt-rule test and the gate table of `docs/roadmap/plan-recheck.md` state the new rule.

## Capabilities

- `roadmap-stage/trace-gate`: a stale line citation whose text is on exactly one other line is accepted as that line, and the job log counts these citations.

## Impact

- The stage job asks for fewer replies for a plan whose evidence is true at a moved line. A citation whose text is on no line, or on two or more other lines, still fails the gate, so the gate still catches false evidence.
- The prompt text changes, so the prompt version changes and the kept plans of the stage job are planned again once.
- No setting, metric or dependency changes.

## Feasibility

- On `origin/main` at 87ae9eefa, `_line_citation_problem` compares the cited text with line `N` only (`cited_line = _line_at(content, int(line))`) and returns `stage_problem_citation_stale` for any other result. No later merge changes this check.
- A replay of the 4 refused stage records of 2026-11-11 (#3387, #3389, #4028, #4043; 11 replies) reads each cited file at the `origin/main` commit of the refusal time with `git show` and runs `_plan_citation_problems`. On the base it returns 17 stale-citation problems, the same paths as the recorded refusals. The 30 stale line citations under them are 29 with the text on exactly one line (for example `src/devops_cli/config/constants.py` 3276 to 3296 and `src/devops_cli/roadmap/refine/refine.py` 744 to 748, as the traces of cause C10 show) and 1 with the text on two lines (`src/devops_cli/roadmap/implement/implement_run.py`, lines 1321 and 1646). With the change, the replay returns 1 problem: the ambiguous citation.
- The golden-set replay (`uv run devops roadmap eval stage --replay`) passes no reader, so it judges no citation. It gives the same result on the base and on the change.

## Existing Tool Considered

No open tool covers a check inside this gate: the gate already reads the staged file through `read_text` and compares text with the lines of that file. A fuzzy-match library can accept a wrong line and adds a dependency. The change deletes `_line_at` and `_line_citation_problem`, and adds `_anchored_line`, `_line_citation`, `_citations` and the `_Citation` record. Written cost: about 25,000 tokens to build, 8,000 tokens to keep and fix, and about 3 hours.

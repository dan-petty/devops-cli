# Proposal: #5881

## Why
The implement job checks the premise of a behavior group at the start of that group (#3417). A false premise of a late group thus comes after the earlier groups passed. On 2026-11-15, the runner Job of item #3453 ran groups 1 to 3 for 53 minutes and opened pull request #5873. At group 4 the check returned the item to New. The withdraw then took the 3 commits off the branch and closed #5873. The comment said that the job "ran no step and wrote no code", and the result line said `tokens=0` for a run of 3198 seconds. Closes #5881.

## What Changes
- The job checks the premise of each open behavior group once, before the first step of the run, at the commit that the run starts from. A false premise thus costs no model request and loses no group that passed in the run. A group whose tasks are all ticked passed in an earlier Job and gets no check.
- The comment of this return says what is true: the run made no model request and wrote no code.
- A return to New keeps `implement.spend`. The Service report of the Job counts the tokens of the run in the result line, the attempt line and the token counter, and then clears `implement.spend` and `implement.spend_counted`. The next plan of the item thus starts with no spend.
- The rule `added_guard` of `src/devops_cli/roadmap/premise.py` does not change: #3453 replaces it with an `Adds:` line.

The comment, the record and the result line are observable, so the change has a spec delta. The change fits one pull request.

## Capabilities
- `roadmap-implement-job/stops`: an added requirement for the time of the premise check.
- `roadmap-implement-job/record`: the requirement on the counted spend changes for a return.

## Impact
- `src/devops_cli/roadmap/implement/implement_run.py`: the premise check and the record of a return.
- `src/devops_cli/roadmap/implement/implement_submit.py`: the report of a returned Job.
- `src/devops_cli/lang/en/messages.py`: the comment of the return.
- `src/devops_cli/roadmap/stores/store.py`, `docs/roadmap/implement.md`: the record keys and the guide.

## Feasibility
Confirmed in the source at `ca62d6a9f`. `_groups` calls `_check_premise(group)` inside the group loop, after the claim check of each group. `_return_to_new` writes `implement.spend` and `implement.spend_counted` as None. `_report` of `implement_submit.py` reads the tokens from `implement.spend` less `implement.spend_counted`, so a return logs `tokens=0`. The evidence of the issue (the runner Job of 2026-11-15 18:40Z to 19:33Z, item #3453, pull request #5873) agrees with this order.

## Existing Tool Considered
No open tool decides when a job of this project checks its plan. The change moves one call in the job and changes one record write and one report write: about 40 lines of code and 4 tests, under 60 000 tokens and one hour. The change deletes the per-group call of `_check_premise`.

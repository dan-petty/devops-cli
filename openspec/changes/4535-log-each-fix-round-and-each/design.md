# Design

## Decisions

- One module, `roadmap/round_log.py`, holds the four lines, so their form is in one place and a Loki query can match them by their first words.
- A line holds numbers, item numbers, names of steps, states and classes. It holds no text of the model and no log text of a Job.
- Each line gives `repo=<owner/repo>` before `item=#<n>`. The Service runs the rows of more than one repository in one process, and two repositories can have an item with the same number. So a Loki query joins by repository and item.
- `stage gate returns` logs only for a reply that the checks refused at least once, both when it passes and when it stays refused. So the pass rate of a return is the count of `result=passed` lines over all lines.
- `stage review round` counts round 0 for the first review and one more for each repair round. A review that the decision-model screen ends with no model review (`Band.CONTINUE`) logs a round with no findings, as `_review` returns it.
- The stage row of `run.py` logs the failed items, from `plan.failed` and `applied.failed`, after it counts the results and before it raises the error of the round.
- The version stands for the image digest of the Service (see the proposal, Feasibility).

## Rejected alternatives

- Read the digest of Deployment `roadmap-service` at the start of the Service: it is a Kubernetes API request in each start, it fails outside the cluster, and the release tag already names the same image.
- Log the failed items in `_record_failures` of `stage.py`: an open pull request of #4491 changes that function, and the row of `run.py` holds the same failures.
- A counter for each event: the issue asks for log lines that a Loki query joins by item and round. A metric with the item number would have an unbounded set of series.

# Design

## Decisions

### The latest run of each check decides
Each event of a pull request, such as a push or a close and reopen, starts its workflows in a new check suite. The REST API lists the latest run of a check in each suite, so the head commit holds one run of a check for each event. The reader keeps the latest run of each check and drops the older runs, whatever their conclusion. A newer pass replaces an older failure, and a newer failure or cancel replaces an older pass. `gh pr checks` shows the same run.

### The time of a run is its `started_at`, else its `completed_at`
A newer run that still runs has a `started_at` and no `completed_at`. If the time of a complete run were its `completed_at`, an old run that completed after the newer run started would win, and an old pass would hide the newer run while it runs. With `started_at`, the newer run wins, and the check stays pending until that run ends. A run with no `started_at` uses its `completed_at`. The reader parses each time with `datetime.fromisoformat` of the standard library.

### A check is a name and an app
Two apps can report a check of one name, and a required status check of GitHub can name the app that must report it. The reader keeps the latest run for each pair of name and app id, so a pass of one app does not hide a failure of another app.

### No run hides a run that it cannot be shown to be newer than
A run with no time stays. Each run at the latest time of its check stays. Both rules keep a failure in the verdict when the reader cannot show that a newer run replaced it.

### Known limit: two workflows with a job of one name
Two workflows of the GitHub Actions app can each have a job of one name. A REST check run gives its check suite and not its workflow, so the reader counts the two jobs as one check, and the newer job decides. On the head of #5357, each of the 25 checks has at most one run in each of the two events, so no two workflows of this repository share a check name there.

## Rejected alternatives

- **Keep the rule of the old filter: drop only a replaced cancel.** Rejected: on #5357 it refused a head whose latest runs all passed, while `devops gh pr checks 5357` showed the check as passed. The two commands disagreed on one head.
- **The time of a complete run is its `completed_at`.** Rejected: an old pass that completes after a newer run starts would hide the newer run while it runs, as the decision above shows.
- **Read the checks with `gh pr checks`.** Rejected: the Service reads with the App token through the REST session and has no `gh` login, and `read_check_runs` must read with `checks: read` only (#2865).
- **Read the workflow of each run, and make a check a workflow and a name.** Rejected: a check run gives only the id of its check suite. The name of the workflow needs one more request for each suite, and the head of #5357 shows no check that needs it.
- **Order the runs by `id`.** Rejected: GitHub documents no order of check run ids, and it documents `started_at` and `completed_at` as the times of a run.
- **Compare the text of the times.** Rejected: the old filter compared the text of `started_at`. `datetime.fromisoformat` reads the ISO 8601 times of GitHub with the standard library.

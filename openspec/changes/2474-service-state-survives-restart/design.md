# Design

## Context

The roadmap Service runs one worker for each lane of each managed repository: 8 repositories and 2 lanes give 16 workers. The workers share `RoundPause` (the halt and the budget hold), `RequestBudget` (the requests of the last hour) and `FailureLedger` (the jobs that failed rounds in a row). Every GitHub request of the process goes through the identity's `GitHubRateLimiter`, from the session and from `run_gh`. The pod mounts PVC `roadmap-service-home` at `/home/devops`, and its data directory is `/home/devops/.data`.

## Decisions

- **Three files beside the schedules.** `service_state_dir()` is `<data dir>/roadmap`, the parent of each `<owner>/<name>/schedule.json`. A GitHub login has no dot, so the names `service-halt.json`, `service-budget.json` and `service-failures.json` cannot be an owner's directory. One file for each piece keeps one writer for each file, so no lock goes across modules, and a person can remove the halt alone.
- **The halt is the file.** A halt record that exists means halted; its content (identity, repository, error class, time) is for a person only. So a record that cannot be parsed still halts. The Service logs one error line at start when it finds the record.
- **A start that finds the halt counts the refusal.** `RoadmapServiceIdentityRefused` (#2496) fires while `devops_cli_service_identity_refused_total` is above 0, and a new process starts the counter at 0. Without a count at start, the alert would stop at a restart while the Service stays halted. The count at start keeps the alert true for the whole halt, and the rule needs no change.
- **The budget keeps rounds, not counts.** Each round adds the time it ended and the requests sent since the round before. The spent count is the sum of the rounds that ended in the window. This gives the same result as before, and a new process can count from any value: the request counter of a new process does not continue the old one when the quota ledger is gone.
- **The ledger keys by a digest.** `_round_input` returns the SHA-256 of the JSON of the changes (kind, number, time) and, for a pushed trigger, the round's time. A poll after a restart reads the same changes, so it gets the same digest.
- **An unreadable record stops the start.** `read_state_record` raises `RoadmapRunError` that names the file and says to repair or remove it. To read it as empty would let the Service send what the record held back.
- **A failed write is one error line.** `keep_state_record` logs an error and the Service goes on with the state in memory. The writes run inside a worker's round machinery, where an exception would end the worker, and `/healthz` would then restart the pod with no halt.
- **`service_jobs(state_dir)` builds the lanes.** It makes one `FailureLedger` for the record and gives it to both lanes. A module-level ledger would need the data directory at import and would carry state from one test to the next.
- **A rate limit holds the limiter.** `hold_requests(wait)` sets a time before which `acquire` schedules no request, for every resource and thread. The session's `retry_wait` calls it for a rate limit (not for a 5xx), and `run_gh`'s backoff calls it for every rate-limit backoff. A worker that is in a round waits at its next request; a worker that starts a round waits at its first request.
- **A header-less 403 to a write is a refused identity.** `_HTTP_CLASSES` takes the request too, and a row after the 401 row reads a 403 to a write with no header that starts with `x-ratelimit-` as `GitHubUnauthenticatedError`. A rate limit and a missing scope come first.
- **Two phrases join the gh-output table.** "installation has been suspended" and "suspended your access" are what GitHub says for a suspended installation. gh relays the text on stderr, where the table reads it.

## Rejected Alternatives

- **Connect a `pause_until` reader again in `serve.py`.** `RoundPause.after` reads a failed round's error. A round that gets a secondary limit does not fail: the session waits and sends the request again, and so does `run_gh`. So a reader of failed rounds sees no limit, and the workers that are in a round would not stop. The limiter is the one place every request goes through.
- **Hold only for a `retry-after` header.** The roadmap store writes through `gh api`, which prints no header without `-i`, so its secondary limits have no `retry-after` to read. GitHub's documentation asks for a wait of at least one minute then, and the backoff of `run_gh` starts at 60 s. A hold for every rate-limit wait covers both paths.
- **Add `-i` to the store's writes so the header rule reads them.** Every write would then parse headers before its JSON on stdout, and each caller of `_write` would change. The phrase in the gh-output table already reads GitHub's refusal of a suspended installation, which is the case the issue names.
- **Apply the header rule to a read.** The issue names a write. A read keeps its existing class (`403-whose-message-says-rate-limit-without-its-headers` in `tests/test_github_errors.py`), and a halt that is wrong stops the Service until a person acts.
- **Keep the hold of the limiter on disk.** A hold lasts the wait of one retry, 60 s to 300 s. The pod takes about that long to restart, and the issue lists only the halt, the budget window and the ledger.
- **SQLite or Valkey for the state.** One process writes three small files. `write_json_file` writes each one atomically, and the schedule already uses it.

- **A gauge of the halt for the alert.** A gauge would need a change of the rule, its promtool tests and the spec `roadmap-service-alerts`. The count at start keeps the counter above 0 for the whole halt with the rule as it is.

## Risks

- A person who restarts the pod to clear a halt finds the halt still there. The error line at start, the alert's description and `k8s/README.md` say to remove the file first.
- A 403 to a write from a proxy in front of GitHub, with no rate-limit header, now halts the Service. The Service sends to GitHub's API origin only (`refuse_other_origins`), so no proxy answers for GitHub.

# Proposal: #4448

## Why

#4448: each `devops roadmap intake` run reads the full `state=all` issue listing of the repository again. The GitHub session keeps the ETag of each page only in memory (#1692), and a CLI run is a new process. On 2026-11-11, the listing phase of one `--plan` call took 67.0 s and 46 requests (46 pages, about 4,500 issues and pull requests), of a 346.6 s call. The #4404 timing table shows a median of 163 s for this phase, the body parse included.

## What Changes

- `devops roadmap intake` keeps a snapshot of the issue listing in `roadmap/listing/<owner>/<name>.json` under the data directory. The snapshot holds the parsed record of each issue and pull request, the version of devops-cli that wrote it, the time of the last full read and a watermark.
- A run reads only the issues changed since the watermark (`state=all&sort=updated&direction=desc&since=<watermark>`), and each changed issue replaces its record. So intake parses only the bodies of the changed issues.
- The new watermark is the earlier of the start of the read and the newest `updated_at` that GitHub gave, less 60 seconds.
- A changed issue that joined or left a parent moves the sub-issue count of that parent by one, because GitHub does not move the `updated_at` of the parent.
- A run reads the whole listing and replaces the snapshot when no snapshot is kept, when it cannot be read, when another version wrote it, when its last full read is 24 hours old or older, and on the new `--full` option.
- The snapshot is written through a temporary file and a rename. A snapshot that cannot be read or written gives a warning that names the file.
- `--dry-run` lists the read of the changed issues and the full read, each with its condition.
- `SnapshotStore` is the seam of the place that keeps the snapshots. The CLI uses a file. The shared store of the Service (#4517) can plug in later. The Service and `devops roadmap run` keep the full read.
- A command option, its output and its requests change, so the change has a spec delta: the new capability `roadmap-intake-listing`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-intake-listing`: the snapshot of the issue listing and the read of the changed issues.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/roadmap/stores/listing_snapshot.py` (new), `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/request_plan.py`
- `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/intake/intake_requests.py`
- `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`
- `docs/roadmap/intake.md`, `docs/commands/roadmap.md`
- A new file under the data directory of each workstation that runs intake: about 5 MB for each 1,000 issues and pull requests, because it holds each body (22.8 MB for this repository on 2026-11-11).

## Feasibility

- GitHub REST documentation, "List repository issues": `since` shows only the issues and pull requests updated at or after the time; `sort` takes `updated`; `direction` takes `asc` or `desc`. A probe on 2026-11-11 (`devops gh api "repos/<repo>/issues?state=all&sort=updated&direction=desc&since=<1 hour ago>&per_page=100"`, devops-cli 0.111.0) gave 47 entries on one page, the newest first.
- The listing is paged by offset. With `direction=desc`, an issue that changes during the read moves to the first page, which the read has; so no unchanged issue moves out of a page that the read has not reached. With `asc`, a change during a read of more than one page moves the later pages back by one, and one issue that did not change is skipped and not read again. So the plan uses `desc`, not the `asc` of the refine section.
- Sub-issues, 2026-11-11: the timeline of #4517 shows `sub_issue_added` at 06:34:19, 06:51:36 and 06:56:48, but its `updated_at` stays 06:31:21. So a parent's count needs the adjustment from its changed sub-issues.
- gidgethub 6.0.0 `cache=` takes any mutable mapping, so a disk store could keep the conditional answers. But the default listing order is by creation, newest first, so each new issue moves every page and changes its ETag. A run then gets no 304 after any new issue, and the 45 pages still pass through the rate limiter, which paces a 304 too (`session_transport.py`).
- The new tests fail on the base: the module and the `--full` option do not exist.

## Existing Tool Considered

- The REST `since` parameter is the open tool that covers the incremental read. The change uses it.
- gidgethub's `cache` mapping, kept on disk: rejected, see Feasibility. It keeps no parsed record either, so the parse of about 4,500 bodies stays.
- hishel, an HTTP cache for httpx: rejected for the same reasons. It still walks every page and keeps no parsed record.
- The snapshot store is built: about 180 lines of source and 300 lines of tests; about 150,000 tokens and 3 hours to build, and about 10,000 tokens a month to keep and fix. The JSON file and the atomic write use the existing `write_bytes_file`, and the records use the existing pydantic `IssueRecord`.
- The change deletes no internal code.

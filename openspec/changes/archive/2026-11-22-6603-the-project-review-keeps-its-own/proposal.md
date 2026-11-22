# Proposal

## Why

A 7-day project review with no intake snapshot sends 49 GitHub requests (#6603), above the limit of 45 of #4692, because the review writes no listing snapshot and pages about 25 pages of Actions runs.

## What Changes

- The review keeps its own listing snapshot under review-listing in the roadmap state directory, saves it after each read, and never writes the intake snapshot.
- The review reads the gap from the later of its watermark and the window start, and from the window start when the window starts before the first window that its snapshot covers.
- The runs reader reads the total of each created slice and splits a slice at the count cap of 2,500. For each slice under the cap, it reads one count for each of the statuses success, failure, cancelled and in progress. A window under the cap costs five requests in place of about 25 pages of runs.
- The shipped catalog's run fact takes its value from the four status counts and its n from the total of the window.
- The result-cap constant goes, and the limit table records the removal. `CONST_ROADMAP_REVIEW_RUN_COUNT_CAP`, 2,500, replaces it. The error message `review_runs_at_cap` stays and names the count cap.
- A 7-day review stays at or under 45 GitHub requests with and without a review snapshot.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-project-review`: The review keeps its own listing snapshot, The runs reader counts the runs of each status, A 7-day review sends at most 45 GitHub requests, The listing reader fills the gap after the snapshot watermark, The runs reader splits a slice that reaches the result cap

## Impact

- Code: `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/roadmap/project_review/readers.py`, `src/devops_cli/roadmap/project_review/dispatch.py`, `src/devops_cli/roadmap/project_review/catalog.yaml`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/project_review/test_review_readers.py`, `tests/roadmap/test_roadmap_limit_classes.py`

## Feasibility

- The probes confirm the cited paths word for word: `The path `src/devops_cli/roadmap/project_review/readers.py` is a file of the staging commit.` and `The path `src/devops_cli/roadmap/stores/listing_snapshot.py` is a file of the staging commit.`
- The premise holds at the staged commit: the probe gives the class line of the review listing as `src/devops_cli/roadmap/project_review/readers.py:97:class _ReviewListing`, and the reader is the only listing reader of the review.
- The review read loads the intake snapshot at `src/devops_cli/roadmap/project_review/readers.py:109:held = self.snapshots.load(repo)`, sends the gap at `src/devops_cli/roadmap/project_review/readers.py:112:return merged(held.issues, read_issues(changed_listing(held.watermark)))`, and writes no snapshot, as the docstring says at `src/devops_cli/roadmap/project_review/readers.py:101:writes no snapshot`.
- The staged schema key is the constant `LISTING_SCHEMA_KEY` at `src/devops_cli/roadmap/stores/listing_snapshot.py:61:LISTING_SCHEMA_KEY`, the first 16 hex characters of the sha256 of the JSON schema of the listing record class `src/devops_cli/roadmap/stores/store.py:class IssueRecord`, per `src/devops_cli/roadmap/stores/listing_snapshot.py:63:).hexdigest()[:16]`, and the snapshot record is `src/devops_cli/roadmap/stores/listing_snapshot.py:77:class ListingSnapshot` with the fields at `src/devops_cli/roadmap/stores/listing_snapshot.py:85:schema_key` and `src/devops_cli/roadmap/stores/listing_snapshot.py:87:watermark`.
- The staged overlap is 60 seconds: `_OVERLAP` at `src/devops_cli/roadmap/stores/listing_snapshot.py:66:_OVERLAP` takes `DEFAULT_ROADMAP_INTAKE_SNAPSHOT_OVERLAP_SECONDS`, which is 60 at `src/devops_cli/config/defaults.py:896:DEFAULT_ROADMAP_INTAKE_SNAPSHOT_OVERLAP_SECONDS`, and the max age is 24 hours at `src/devops_cli/config/defaults.py:895:DEFAULT_ROADMAP_INTAKE_SNAPSHOT_MAX_AGE_HOURS`.
- The store seam is `src/devops_cli/roadmap/stores/listing_snapshot.py:91:class SnapshotStore` with the file store `src/devops_cli/roadmap/stores/listing_snapshot.py:105:class FileSnapshotStore`, and the intake snapshot directory name is listing at `src/devops_cli/roadmap/stores/listing_snapshot.py:57:_SNAPSHOT_DIRNAME`.
- The review builds the intake store at `src/devops_cli/roadmap/project_review/dispatch.py:185:snapshots = context.snapshots or FileSnapshotStore(snapshot_root())` and holds no review store, since `src/devops_cli/roadmap/project_review/dispatch.py:104:class ReadContext` has no such field.
- The runs reader counts each page it reads at `src/devops_cli/roadmap/project_review/readers.py:184:reads.add(ReaderKind.GITHUB_RUNS)` and splits at the cap it reads at `src/devops_cli/roadmap/project_review/readers.py:177:cap = DEFAULT_ROADMAP_REVIEW_RUN_RESULT_CAP`, whose staged value is 1000 at `src/devops_cli/config/defaults.py:901:DEFAULT_ROADMAP_REVIEW_RUN_RESULT_CAP`.
- The shipped run fact takes its value from the run list at `src/devops_cli/roadmap/project_review/catalog.yaml:114:.workflow_runs` and defines n as the total at `src/devops_cli/roadmap/project_review/catalog.yaml:120:n is the sum`.
- The repeat text of the runs fact is `src/devops_cli/roadmap/project_review/dispatch.py:500:MESSAGES.roadmap.review_plan_each_slice`, its message is at `src/devops_cli/lang/en/messages.py:6990:review_plan_each_slice`, and the cap error is at `src/devops_cli/lang/en/messages.py:7015:review_runs_at_cap`, used only at `src/devops_cli/roadmap/project_review/readers.py:188:MESSAGES.roadmap.review_runs_at_cap.format(`.
- The limit table that records a removed constant is at `tests/roadmap/test_roadmap_limit_classes.py:50:REMOVED` and holds its entry at `tests/roadmap/test_roadmap_limit_classes.py:707:DEFAULT_ROADMAP_REVIEW_RUN_RESULT_CAP`.
- The retired-lane scan removes each `listing-<name>` directory that is no lane, at `src/devops_cli/roadmap/run.py:2230:retired += [path for lane, path in lane_snapshot_dirs(state_dir).items() if lane not in running]`, so the review store is named review-listing.
- The read counts reach the data file at `src/devops_cli/roadmap/project_review/data.py:110:reads`.
- The documentation group edits the review line at `docs/ROADMAP_WORKFLOW.md:500:gives the git facts of a review window`.
- The three listing tests that the group updates are `tests/roadmap/project_review/test_review_readers.py:180:test_the_listing_reads_the_issue_after_the_watermark_once_and_keeps_the_snapshot`, `tests/roadmap/project_review/test_review_readers.py:194:test_an_old_snapshot_of_this_schema_gives_only_the_changes_after_its_watermark` and `tests/roadmap/project_review/test_review_readers.py:210:test_with_no_snapshot_of_this_schema_the_listing_reads_the_changes_since_the_window_start`, and they save their snapshot through `tests/roadmap/project_review/test_review_readers.py:142:def _held(`.
- `read_listing` sends each page through the session of the read context; its precondition is a client of GitHub and a network.
- `read_runs` sends its five count requests through the same session; its precondition is a client of GitHub and a network.
- `run_review` reads the git facts of the window from the checkout before the readers run; its precondition is a checkout of the repository.
- `review_listing` and the save of the review store write under the roadmap state directory; their precondition is a writable state directory, and no network.
- The verify commands `uv run devops ci test` and `uv run devops ci docs` run tools of the image: uv and pytest are runner tools, and no program of the plan is NOT_IN_RUNNER. A failing test is class test (repair), a lint finding lint (repair) and a type error types (repair). The pod sets readOnlyRootFilesystem true, runAsNonRoot true, capabilities.drop ALL, allowPrivilegeEscalation false and seccompProfile RuntimeDefault, and the tests write only under the pytest temporary directory.
- GitHub gives an exact count for each run status above the 1,000 result cap: the request `repos/dan-petty/devops-cli/actions/runs?per_page=1&branch=main&event=push&created=>=<7 days ago>&status=<status>` gave `total_count` 1830 for success, 29 for failure, 71 for cancelled and 12 for in_progress on 2026-11-21, and 1942 with no status filter, which is the sum of the four. A status with no run, skipped, gave 0. The 45-request limit is the issue body of #4692, and the 49 measured requests are the issue body of #6603.
- First real check: run `uv run devops roadmap review run --last 7d` twice on a checkout with no review snapshot, then read `collection.reads` of each written data file; the first sum is at most 45 and the second listing count is lower.
- First real check: run `uv run devops roadmap review run --last 7d` with no snapshot, then check that the runs fact holds four status counts whose sum is its n, and that the roadmap state directory holds one review snapshot for the repository.
- First real check: run `uv run devops roadmap review run --last 7d --dry-run`, then check that the request plan lists the total and one count request for each status, for each created slice.
- The issue can be built as written: each cited path, class and constant exists at the staged commit, and no commit renamed or removed them.

## Existing Tool Considered

No open, maintained tool or library covers a GitHub issue-listing snapshot with a watermark for this command. The change reuses the project's snapshot store, snapshot record and watermark rule, and deletes the runs page loop, `_slice_path` and the result-cap constant. It builds about 40 lines of code and about 80 lines of test: 15k tokens and 3 hours.

## Dependencies

- #4692: it adds the catalog and the listing and runs readers that this plan changes, so its requirements must be in the tree first.

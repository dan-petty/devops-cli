# Proposal

## Why

The row that watches plan drafts re-reads a head with a failed check in each round. A failed check does not change until a push or a new run, so the row spends GitHub requests with no result, 1841 in one repository in one day. The row that owns this work now is `watch`, and it waits one flat 30 minutes, so the wait never grows and a failed head stays on the same cadence. #3671

## What Changes

- `src/devops_cli/roadmap/watch_row.py` records the failed-head wait in minutes in the watch ledger entry and grows it 15, 30, 60, then 60.
- `src/devops_cli/roadmap/watch_row.py` clears the wait and reads a head at once when the head or the base branch moves, and records no wait for a verdict that is not a failed head.
- `tests/roadmap/test_roadmap_watch_row.py` holds the interval: a draft plan pull request with a failed check records 15 minutes, then 30, then 60, then 60.
- `docs/CLUSTER.md` item 18 states the growing failed-head wait and the clear on a moved head.
- The spec delta changes the requirement `Watch maintains a ledger with failed head backoff` of the capability `roadmap-watch-row`, and no `stage_ready` row comes back.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-watch-row`: Watch maintains a ledger with failed head backoff

## Impact

- Code: `src/devops_cli/roadmap/watch_row.py`
- Documents: `docs/CLUSTER.md`
- Tests: `tests/roadmap/test_roadmap_watch_row.py`

## Feasibility

- The probes show that the path of the issue is gone, word for word: "The path `src/devops_cli/roadmap/stage_ready.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_ready.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it."
- `read_file` of `src/devops_cli/roadmap/run.py` lines 1032-1148 gave the whole due table: `src/devops_cli/roadmap/run.py:1032:STATUS_LANE_ROWS: tuple[JobRow, ...] = (` holds `metrics`, `implement`, `plan_drift`, `watch`, `stage`, `release_comments`, `github_status` and `cloudflare_status`; with `TRIAGE_LANE_ROWS` (`intake`) and `MODEL_LANE_ROWS` (`retitle`, `fix_plan`, `refine`, `alternatives`) the table holds 13 rows, and no `stage_ready` row reads a draft.
- The `references` answer for `mark_stage_ready` named 5 files with no files left out, and outside `openspec/changes/archive/` only the module and its two test modules hold the name, so the retired row has no caller in `src/`: `src/devops_cli/roadmap/stage/stage_ready.py:def mark_stage_ready`.
- The row that replaced it already backs a failed head off with one flat value: `src/devops_cli/roadmap/watch_row.py:338:next_read_iso = (ctx.current_time + timedelta(minutes=30)).isoformat()`, and item 18 of the cluster document states that value: `docs/CLUSTER.md:49:maintains a ledger `watch.json` with 30-minute failed-head backoff (#3671)`.
- So the plan delivers the growing wait in the row that owns the work now, `watch`: 15 minutes after the first failed read of a head, then 30, then 60, held at 60, and a moved head or base clears it. The plan restores no `stage_ready` row and writes no `stage_ready.*` key.
- The staged constants that the plan relies on: `src/devops_cli/config/defaults.py:1123:DEFAULT_ROADMAP_WATCH_INTERVAL_MINUTES: int = 3` is the interval of the row, and `src/devops_cli/config/constants.py:3721:CONST_ROADMAP_WATCH_LEDGER_FILENAME: Final[str] = "watch.json"` is the ledger file that holds the wait.
- The wait lives in the ledger entry of the row: `src/devops_cli/roadmap/watch_row.py:119:class WatchLedgerEntry(BaseModel):` holds `src/devops_cli/roadmap/watch_row.py:124:next_read_at: str | None = None`, and the change adds the wait in minutes beside that field.
- The row gives a failed head one verdict: `src/devops_cli/roadmap/steps/watch.py:38:class PRVerdict(StrEnum):` holds the values, and `src/devops_cli/roadmap/steps/watch.py:43:FAILED = "failed"` is the value that starts the wait. A running check keeps the pending verdict (`src/devops_cli/roadmap/steps/watch.py:203:pending = [c for c in items if c.bucket == CheckBucket.PENDING]`), so it records no wait.
- The spec text that the change replaces: `openspec/specs/roadmap-watch-row/spec.md:23:It SHALL NOT re-read checks for a failed head within 30 minutes unless the head commit or base branch moves.`
- The case that holds the interval today: `tests/roadmap/test_roadmap_watch_row.py:158:assert entry1.next_read_at == (t0 + timedelta(minutes=30)).isoformat()`, and the change updates it to the 15-minute first wait.
- The issue names `k8s/README.md` as the document of the `stage_ready` item, but `search_code` for `waiting draft` and for `requests a round` returned `No match.` over the whole commit, and the only line of that file that holds `every 3 minutes` is `k8s/README.md:1392:# CronWorkflow rag-ingest: runs WorkflowTemplate rag-ingest every 3 minutes`, so that file holds no `stage_ready` item. The `12 an hour` figure sits in an archived change, `openspec/changes/archive/2026-10-31-2865-service-marks-stage-pr-ready/proposal.md:43:2 requests every 10 minutes, 12 an hour, against`. The living item that states the row and its wait is `docs/CLUSTER.md:49`.
- The webhook clear that the Expected of the issue names is the open item #5653 (`feat(roadmap): clear the stage_ready wait on a webhook event`), found by `find_issues` for `scoped update pull_request webhook`, and `src/devops_cli/roadmap/run.py:1207:SCOPED_UPDATES: Mapping[tuple[str, str], ScopedUpdate] = MappingProxyType(` holds the `issues` events only, so this plan leaves that part out and the row sees a push at its next round.
- The plan calls `watch_round(store, repo=..., ledger_path=..., now=...)` of `src/devops_cli/roadmap/watch_row.py`; its arguments need a client of GitHub, and the case doubles that edge with `GitHubApiFake` of `tests/support/fakes/github.py`, so the step needs no checkout, no network and no cluster.
- The plan adds and calls the pure function `_next_backoff_minutes(recorded: int) -> int`; its arguments need no checkout, no client and no network.
- Both verifies are existing rows of the image: `uv run devops ci test tests/roadmap/test_roadmap_watch_row.py` runs the `test` row, and `uv run devops ci docs` runs the `docs` row of `src/devops_cli/commands/ci.py:930:name="docs",`. The image lists `devops`, `uv`, `python` and `pytest` in its Runner tools, no program of the plan is `NOT_IN_RUNNER`, a failed run is the existing class `test` of the row, and the pod keeps `readOnlyRootFilesystem: true` with the ledger written under the `tmp_path` of the case.
- The two findings of `problem` are answered at their place: the decision about the failed verdict gives the class line `src/devops_cli/roadmap/steps/watch.py:38:class PRVerdict(StrEnum):`, and the rejected alternative about the item job record names no record-key class.
- The `stage_ready` module and its two test modules stay as they are, and no group touches them: `src/devops_cli/roadmap/stage/stage_ready.py`, `tests/roadmap/stage/test_roadmap_stage_ready.py` and `tests/roadmap/stage/test_roadmap_stage_ready_jev.py`.

## Existing Tool Considered

No open, maintained tool covers a wait that lives in the row's ledger across rounds: `tenacity` and `backoff` retry one call inside one process, and this wait must skip a later round of the Service and survive a restart. The change builds its own code, about 25 lines of source and about 60 lines of tests: about 6k tokens to build, keep and fix, and about 3 hours of elapsed time.

## Dependencies

- PR #5946 changes `src/devops_cli/roadmap/stores/store.py`, and this plan adds no key to that store: the wait lives in the watch ledger.
- PR #5959 changes `src/devops_cli/roadmap/stores/store.py`, `docs/CLUSTER.md` and `k8s/README.md`, and this plan edits item 18 of `docs/CLUSTER.md` and no store key.
- PR #5963 changes `src/devops_cli/roadmap/stores/store.py`, and this plan adds no key to that store.
- PR #5981 changes `docs/CLUSTER.md`, and this plan edits item 18 of that document.

# Proposal

## Why

The Service spends its 4000-request hourly budget on polling for issue, pull request and check state that GitHub already pushes, so rounds wait all day: 693 holds in 24 hours on 2026-11-16, and each row reads the same issue again between two changes. #6013 asks the project brain to keep the GitHub objects that rows read, written by webhooks, so a row reads GitHub only on a miss, for a write, or after the one-hour limit. This change delivers the issue object, its per-row counters and its conditional revalidation; the pull request and check objects go to #6630.

## What Changes

- One brain entry for each issue of a Service repository, under the key form of `RepoRef.valkey_key("brain-issue", <number>)` and a `TieredMapping` over the shared tier, in the new `src/devops_cli/roadmap/stores/brain_issues.py`.
- `BrainStore.ISSUE` in `src/devops_cli/config/constants.py`, and the two bounds `DEFAULT_BRAIN_ISSUE_TTL_SECONDS` and `DEFAULT_BRAIN_ISSUE_MAX_AGE_SECONDS` in `src/devops_cli/config/defaults.py`.
- A new counter `devops_cli_brain_cache_total{row,result}` in `src/devops_cli/telemetry/instruments.py`, with its row in `docs/TELEMETRY.md`, so each row counts its cache hit and its cache miss beside `devops_cli_github_requests_total`.
- The read of an issue in `src/devops_cli/roadmap/stores/github_store.py` reads the entry first, sends a conditional read with the stored `ETag` after one hour, and fills the entry on a miss or after a write.
- The label writes and the `PATCH` writes of the store fill the entry, because a label write keeps no answer of the issue.
- The roadmap consumer writes the entry from the `issues` payload before it wakes a lane, in `src/devops_cli/server/routes/webhooks.py`, and `src/devops_cli/models/webhooks.py` gives the payload the title, body, state and update time of the issue.
- `docs/CLUSTER.md` describes the cached issue, its key, its life, its writers, its revalidation and its counter.
- The change caches issue objects only: a pull request or a check object needs a new consumer event and a person's change of each repository hook, so #6630 takes that part.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-brain/shared-cache`: The brain holds the issue that a row reads, A row reads the cached issue before GitHub, A Service write fills the cached issue, A row reads GitHub when the shared tier is down, The cached issue key names its repository and number, A revalidation leaves an unchanged issue in the brain, The cache counts a hit and a miss for each row, A quiet Service repository stays inside the request budget, Each value has a bound and each key a TTL
- `roadmap-service-webhooks`: The roadmap consumer writes the cached issue before it wakes the lane

## Impact

- Code: `src/devops_cli/roadmap/stores/brain_issues.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/models/webhooks.py`
- Documents: `docs/TELEMETRY.md`, `docs/CLUSTER.md`
- Tests: `tests/roadmap/stores/test_brain_issues.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/stores/test_github_store_brain.py`, `tests/server/routes/test_webhooks_brain.py`

## Feasibility

- The probes hold these lines word for word: `RepoRef` defines no field `valkey_key` in `src/devops_cli/github/repo_ref.py`; `RepoRef` defines no field `valkey_patterns` in `src/devops_cli/github/repo_ref.py`. A `read_file` of the reference module shows `src/devops_cli/github/repo_ref.py:201:def valkey_key(self, kind: str, ident: str | None = None) -> str:` and `src/devops_cli/github/repo_ref.py:212:def valkey_patterns(self) -> tuple[str, str]:`, so a dataclass field is not a method, and `RepoRef(repo).valkey_key("brain-issue")` gives `roadmap:v1:brain-issue:<owner>/<name>`.
- The premise of the issue holds for the issue object: the read of an issue by number sends one GitHub request today, `src/devops_cli/roadmap/stores/github_store.py:839:found = self._read_or_none(issue_args(self._repo, number), _ISSUE, f"issue #{number}")` through `src/devops_cli/roadmap/stores/github_store.py:589:def issue_args(repo: str, number: Number) -> list[str]:`, and `src/devops_cli/roadmap/stores/github_store.py:833:found = self.issue(number)` is how `item` follows it, so every row that reads an item sends that request again.
- No brain entry of an issue exists at the staged commit: `file_symbols` of the store lists no symbol that names the brain, `src/devops_cli/roadmap/stores/github_store.py:836:def issue(self, number: int) -> IssueRecord | None:` is the one read of an issue and it goes to GitHub, and `src/devops_cli/valkey/tiered.py:138:return f"{self.prefix}{_SEPARATOR}{key}"` builds a key from a prefix, with no GitHub object behind it.
- A label write keeps no answer of the issue: `src/devops_cli/roadmap/stores/github_store.py:1186:self._write(label_args(self._repo, number, label), f"label #{number} {label}")` writes the label and updates only the listing that the store holds, so this plan writes the entry from that record in `label_issue` and `unlabel_issue`, and from `src/devops_cli/roadmap/stores/github_store.py:1394:def _kept(self, issue: _IssuePayload) -> IssueRecord:` for a `PATCH`.
- The mapping needs no new cache class: `src/devops_cli/valkey/tiered.py:109:def __init__(` takes `prefix` as an argument and `src/devops_cli/valkey/tiered.py:136:def shared_key(self, key: str) -> str:` builds `<prefix>:<key>`, so a mapping whose prefix is the repository key of an issue gives `roadmap:v1:brain-issue:<owner>/<name>:<number>`.
- The row of a read comes from the request in flight: `src/devops_cli/github/request_scope.py:63:return {"repo": scope.repo, "row": scope.row}` gives the bounded row, so `devops_cli_brain_cache_total{row,result}` counts a hit and a miss for each row while `devops_cli_brain_reads_total` keeps its `store` and `result` labels.
- One simulated hour holds 12 rounds of 5 minutes, so six issues read in each round send six GitHub requests, fewer than 20; the real row count of a quiet repository is not checked by any tool of this run.
- The conditional read reads the status line that `gh api --include` prints, as `src/devops_cli/github/hook_deliveries.py:94:def _next_endpoint(` does, and reads the status of a failed command with `src/devops_cli/github/error_classifier.py:354:def gh_http_status(output: str) -> int | None:`. A `304` keeps the stored issue: `src/devops_cli/github/rate_limiter.py:805:with 304 does not count against its primary rate limit, so `count_request` calls `refund`` states GitHub's rule, and `src/devops_cli/github/rate_limiter.py:1720:if status == HTTPStatus.NOT_MODIFIED and refund is not None:` refunds the place of a session `304`.
- Precondition of `src/devops_cli/valkey/cache.py:259:def shared_cache_tier()` and of `src/devops_cli/valkey/tiered.py:140:def __getitem__(self, key: str) -> V:`: a client of the cache Valkey. A test installs a fake tier, so the step reaches no network.
- Precondition of `src/devops_cli/roadmap/stores/github_store.py:836:def issue(self, number: int) -> IssueRecord | None:` and of the new `_revalidate_issue`: a GitHub client and a network. The tests pass a fake runner of the type `src/devops_cli/roadmap/stores/github_store.py:119:class GhRunner(Protocol):`, so they reach no network.
- Precondition of `src/devops_cli/roadmap/stores/github_store.py:1184:def label_issue(self, number: int, label: str) -> None:` and of `src/devops_cli/roadmap/stores/github_store.py:1394:def _kept(self, issue: _IssuePayload) -> IssueRecord:`: a GitHub client and a network. The tests pass the same fake runner.
- This run ran no command against GitHub. The first command that the implementation runs against the real system is `gh api --include -H 'If-None-Match: <etag>' repos/<owner>/<name>/issues/<number>`, run twice on one issue of a Service repository, to confirm the status line and the exit code that a `304` gives.
- The second check is `uv run devops ci test tests/roadmap/stores/test_github_store_brain.py`, which doubles the tier and the runner and reaches no network; the third is a query of `devops_cli_brain_cache_total{row,result}` and `devops_cli_github_requests_total{repo,row}` in Prometheus after one hour of Service rounds.
- The verify commands `uv run devops ci test` and `uv run devops ci docs` run `pytest`, `ruff` and `mypy` from the runner image; the failure classes are `test`, `lint` and `types`; no program of the plan is `NOT_IN_RUNNER`, and the pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false` and `capabilities.drop: ALL`.
- The issue's expected behavior names pull request and check objects, and its refine block moves them to #6630 because `src/devops_cli/config/constants.py:4023:CONST_ROADMAP_WEBHOOK_EVENTS: Final[frozenset[str]] = frozenset(` holds the `issues` events only; this plan caches the issue object and plans no code for the others.
- Not checked: the live request count of a quiet repository, the live deliveries of a repository hook, and the exit code that `gh api` gives a `304`.
- The tiered mapping supplies the key form, the TTL and the counters, so the plan adds no cache class of its own and cites only the line of the mapping and its factory.

## Existing Tool Considered

hishel caches an HTTP answer with an ETag validator and covers only a conditional read; the alternatives block of the issue records its verdict as rejected under ADR 0023, and it has no webhook write, no GitHub issue schema and no per-row read-through. The plan reuses the shared cache tier, the tiered mapping and the brain counters of the project and builds about 200 lines of its own: about 40k tokens to build, about 15k tokens a month to keep and fix, and about 3 days of elapsed work.

## Dependencies

- `devops_cli_github_requests_total` is also sent by src/devops_cli/github/client.py, src/devops_cli/github/rate_limiter.py, src/devops_cli/github/request_scope.py, src/devops_cli/telemetry/instruments.py, src/devops_cli/docs/generator.py, docs/TELEMETRY.md, docs/SERVICE_PATTERNS.md, openspec/specs/github-api-metrics/spec.md and the Service dashboards; this change reads that counter and changes two of those files, `src/devops_cli/telemetry/instruments.py` and `docs/TELEMETRY.md`, without changing its series.

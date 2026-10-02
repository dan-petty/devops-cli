# Task: One Roadmap Store Reads and Writes Items, Releases and Board Fields (#768)

**Issue**: [#768](https://github.com/dan-petty/devops-cli/issues/768)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/github

## Description
Releases (milestones) were read and written five ways, and a failed read often looked empty. `devops gh milestones edit v0.2.25 --description x` closed v0.2.25 whenever a token resolved, because `GitHubClient.edit_milestone` defaulted `state="closed"`. No roadmap job could be tested without patching `run_gh`. This adds the one store that the roadmap jobs (#739-#744) and the service (#752) read and write the roadmap through, and moves the Releases slice onto it.

- `src/devops_cli/roadmap/store.py` holds the runtime-checkable `RoadmapStore` Protocol, the frozen models (`Release`, `Item`, `Candidate`, `Change`), the rules both adapters apply, and `get_roadmap_store`, the one factory callers use. A Release is a milestone whose title parses as a `packaging` version, so `0.2.25` and `v0.2.25` find the same one and v0.2.9 sorts before v0.2.10. An Item is an issue of this repository that is on the board. A Candidate is an open issue of this repository that is not on the board.
- `GitHubRoadmapStore(repo, board_owner=None, board_number=None, runner=run_gh)` (`roadmap/github_store.py`) runs every command through the injected runner with `use_cache=False`. REST listings put their endpoint directly after `api --paginate` with `per_page=100` (`DEFAULT_GH_REST_PER_PAGE`). The board comes from `gh project item-list --limit 5000` (`DEFAULT_GH_PROJECT_ITEM_LIMIT`), and a listing shorter than its `totalCount` raises. Board items are joined by number with the REST issue listing, which supplies state and Release. Pull requests, draft issues and other repositories' items are never Items. Issue events are read one page at a time, newest first, and the read stops at the first event older than its argument. A non-zero exit, malformed JSON or a short read raises `GitHubOperationError`, and a rate-limit message raises `GitHubRateLimitError`. Without a board, Release operations work, and Item reads and writes raise.
- Each Item write sets the field, then the board's `Job record` text field, which holds JSON with the last value the store set for each field (ADR 0002). The store reads the field options and the Item's board entry before it writes anything. A value that isn't one of the field's options, an Item that is not on the board, or a board with no `Job record` field raises before any call that changes GitHub. The new value joins the record the board holds at write time, not the one on the `Item` the caller passes in. Two writes from one read therefore both stay recorded. The field is in `.github/project-template.json`. On board 2 a person creates it once with `gh project field-create 2 --owner dan-petty --name "Job record" --data-type TEXT`.
- `InMemoryRoadmapStore` (`roadmap/memory_store.py`) keeps the same promises with no I/O. `seed_issue` opens issues and pull requests, and `as_actor("alice")` writes as a person: the write records a change under that person's name and leaves the job record alone.
- `devops gh milestones list`, `status`, `close`, `edit` and `sync` and the milestone close after `devops release tag --push` now use the store. When GitHub can't be read, `list` exits 1 and names the failed read. `edit` sends only the fields it is given, and like `close` it takes a version, with or without the `v`, never a milestone number. `release tag --push` closes the Release in the tagged repository's origin (`get_repo_origin_name(repo_root)`), not the current directory's. It warns only on a `DevOpsCLIError`. `_closed_milestone_titles` (`github/release_epics.py`) reads `releases()`, and a failed read raises instead of returning an empty set.
- Deleted, without shims: the `client: Any` wrappers in `github/milestones.py` and their re-exports in `github/__init__.py`, `_get_repo_milestones` and `_close_milestone_gh_cli` in `commands/gh.py`, the milestone methods of `GitHubClient` and `GhCliClient`, and the test-only REST board read in `github/projects.py`.
- `tests/conftest.py` turns the factory into a refusal for the whole session (`github_roadmap_factory`), so no test opens the GitHub store over the developer's `gh` login. A test that drives a roadmap command requests `roadmap_store`, the in-memory adapter that every store a command opens reads and writes. `roadmap_store_repos` lists the repository each store was opened for. `unreadable_github_roadmap` opens the GitHub store over a runner that exits 1. The milestone CLI tests pass a `--repo` that is not this checkout's origin and assert the repositories opened. A command that ignored `-R`, or a `release tag` that stopped resolving the tagged repository, failed 5 tests and 1 test respectively.

## Acceptance Criteria
- [x] `RoadmapStore` is a runtime-checkable `Protocol` that `InMemoryRoadmapStore` and `GitHubRoadmapStore` satisfy: `mypy --strict` passes on `src`, and `test_both_adapters_are_roadmap_stores` checks `isinstance` for both.
- [x] The contract suite (`tests/test_roadmap_store_contract.py`, 26 tests, in-memory adapter) has one test per promise. The cases cover version lookup with and without the `v`, unknown versions, duplicate creates, version order, an edit that leaves the state alone, Items in a Release, the Backlog, Candidates, refused option values, the job record against a person's change, an empty record for an Item no job wrote, and one joined-Release change by `alice`. It also checks that two writes from one Item read keep both fields in the record.
- [x] The GitHub adapter's stub-runner tests (`tests/test_roadmap_github_store.py`, 37 tests) answer from recorded `gh` output in `tests/fixtures/roadmap/`. They pin each write's argv and an edit with no `state`. They check that `api --paginate` is followed by an endpoint carrying `per_page=100`, and that 46 recorded milestones (more than one page at the 30-row default) resolve `0.2.25` and `v0.2.25` to number 43. A board holding an issue, a pull request, a draft issue and a foreign issue yields one Item. They cover a closed Item in a Release, Candidates, a refused option with no write, and the field-then-record write. Two writes from one read keep both fields, against a board that stores each record write. A board with no `Job record` field raises before any write, and so does an Item that is not on the board. A failed exit, malformed JSON and a short board listing each raise. Every read passes `use_cache=False`, and `changes_since` pages and filters events.
- [x] `rg -n "^\s*(import github|from github )|GitHubGraphQLClient|httpx" src/devops_cli/roadmap` prints nothing.
- [x] `rg -n "except TypeError|client: Any" src/devops_cli/github/milestones.py` prints nothing.
- [x] `rg -n "_resolve_milestone_target_number|_close_milestone_gh_cli|_get_repo_milestones|_fetch_project_item_urls|_extract_urls_from_project_items|SingleArgClient" src tests` and `rg -n "def (get|create|edit|close)_milestones?\(" src/devops_cli/github/client.py` print nothing.
- [x] No test in `tests/test_github_milestones.py`, `tests/test_gh_issues_milestones.py`, `tests/test_gh_cmd.py` or `tests/test_github_client.py` patches `run_gh`, `GitHubClient` or `_get_github_client` to drive a milestone command. The remaining hits cover `gh issues` (`_resolve_milestone_number` stays with `gh issues create` and `edit`), labels, runs, rate limit, `gh api` and the non-milestone `GitHubClient` methods.
- [x] `devops gh milestones edit v0.2.25 --description x` leaves v0.2.25 open: `test_cli_gh_milestones_edit_leaves_the_release_open`.
- [x] When GitHub can't be read, `devops gh milestones list` exits 1 and names the failed read instead of printing "No milestones found": `test_cli_milestones_list_names_a_failed_read`, with a stub runner that exits 1.
- [x] The two new test files run in under 1 s in total, and the rewritten milestone tests take less time than the ones they replace (see Measurements).
- [x] `uv run devops ci` passes within its 5-minute budget.

## Measurements
Each figure is the sum of the setup, call and teardown durations that `--durations=0` reports, over three runs in one process each (`-n0`). The machine was otherwise idle: 16 cores, one-minute load 1.0 to 1.2. "Before" is a `git archive` export of 44d1f90 run with the same interpreter. Before and after runs alternated.

**The two new files** (`uv run pytest -n0 --durations=0 tests/test_roadmap_store_contract.py tests/test_roadmap_github_store.py`, 63 tests):

| Run | 63 tests, without the session setup | Session setup, charged to the first test | `--durations=0` total |
| :--- | ---: | ---: | ---: |
| 1 | 192 ms | 1,936 ms | 2,128 ms |
| 2 | 174 ms | 1,694 ms | 1,868 ms |
| 3 | 168 ms | 1,682 ms | 1,849 ms |

The setup caveat: `--durations=0` charges the first test in a pytest process with the session-scoped fixtures in `tests/conftest.py` and the imports they pull in. Run alone, one unrelated test (`tests/test_agent_task_files.py::test_task_files_exist`) pays 2.7 to 2.9 s for that setup at 44d1f90 and 2.9 s now. The cost belongs to the session, not to these files. In the gate each xdist worker pays it once, whatever tests it runs.

**The rewritten milestone tests**, on the four files the issue names (`tests/test_github_milestones.py`, `tests/test_gh_issues_milestones.py`, `tests/test_gh_cmd.py`, `tests/test_github_client.py`). A test counts as rewritten when it was removed or added, or its function differs from 44d1f90's:

| Run | Before: 25 removed or changed | After: 18 added or changed | Before: all 84, without session setup | After: all 77, without session setup |
| :--- | ---: | ---: | ---: | ---: |
| 1 | 953 ms | 373 ms | 3,743 ms | 3,460 ms |
| 2 | 953 ms | 338 ms | 3,747 ms | 3,171 ms |
| 3 | 929 ms | 337 ms | 3,651 ms | 3,172 ms |

Measured the same way, the rewritten tests in `tests/test_release.py` and `tests/test_release_epics.py` took 451 to 469 ms before (4 tests) and 225 to 261 ms after (5 tests). `test_release_tag_push_and_errors` went from 245 to 254 ms to 70 to 90 ms, including the two `git` calls that now give its project an origin.

## Checks Against Live GitHub
The issue lists the read-only check against this repository and the write check against a scratch repository under *Checks a person runs*. They are not tests and are not part of the gate. The read-only check ran on 2026-10-02 against this repository. The store printed `16 0` (Items in v0.2.25, Candidates), and the two `gh` commands printed `16` and `0`. It also read 46 Releases, sorted v0.0.1 to v0.3.5, and resolved `0.2.25` and `v0.2.25` to the same milestone. Item writes on board 2 need the `Job record` field created first, as described above.

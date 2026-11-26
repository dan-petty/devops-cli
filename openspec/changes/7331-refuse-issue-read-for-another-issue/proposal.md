# Proposal: #7331

## Why

A read of an issue by its number can answer with another issue (#7331). GitHub redirects the read of an issue that was transferred to another repository, and the answer then holds the number and the repository of the issue at its new place. `GitHubRoadmapStore` takes that answer as the issue that it asked for: `issue`, `item`, `read_issue_body`, `pull_title` and the read that each write makes first give a record with the number of the answer. The listing snapshot also keeps the record of a transferred issue as an open item until the next full read, at most 24 hours later, so a row selects the number in each round.

## What Changes

- `GitHubRoadmapStore` compares the number and the repository of the answer with the request, in one place (`_answered`). The repository of an answer comes from `repository_url`, else from `url`, else from the page URL `html_url`. `RepoRef` compares the names, so their case does not count. An answer that names no repository is compared by its number only.
- An answer that names another issue is no issue of the repository, as a missing one. `issue`, `item` and `pull_title` give None. `read_issue_body` and each write that reads the issue first raise the `GitHubOperationError` of a missing issue, before any write request. The store logs one warning that names the requested number.
- The comparison covers each place that takes an issue payload for a number: the plain read, the conditional read with `If-None-Match`, the read of each write, the read-back of a record write, the title read of a pull request, and the answer of the `PATCH` of an issue.
- The store drops what it holds of a number that is no issue of the repository, for a 404 answer too: the record in its listing, the record in the later reads of the listing of its lane, and the entry in the brain. `IncrementalListing` keeps such numbers for the life of the lane and leaves their records out of each read and of the snapshot that the read keeps, until GitHub lists the number as changed or until the next full read.
- The store uses a brain entry only when its record names the requested number and the repository of the store. It removes any other entry and reads GitHub.
- `docs/CLUSTER.md` gives the rule in its paragraph about the issue cache.

A consumer observes the result of a read, the requests of a write and the records of the snapshot, so the change carries spec deltas. It fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-store-issue-read`: An issue read compares the answer with the request, The repository of an answer comes from its URL fields, A conditional read compares its answer, A refused answer logs the requested number, A write is refused when its read answers with another issue, The answer of an issue write is compared with the request, A row sends no write for an item whose read answers with another issue

### Modified Capabilities

- `roadmap-intake-listing`: A number that is no issue of the repository leaves the listing, A dropped number stays out until GitHub lists it
- `project-brain/shared-cache`: The brain holds no entry of a number that is no issue of the repository, The store uses an entry only for the issue that it names

## Impact

- Code: `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/roadmap/stores/brain_issues.py`, `src/devops_cli/roadmap/project_review/readers.py`
- Tests: `tests/roadmap/stores/test_roadmap_github_store_issue_answer.py` (new), `tests/roadmap/test_roadmap_rows_issue_answer.py` (new), `tests/support/fakes/github_repository.py` (`GitHubFake.move_issue`), and the 3 answers of `tests/roadmap/stores/test_github_store_brain.py` that named another repository than their store
- Documents: `docs/CLUSTER.md`
- GitHub requests: none is added. A number that is no issue of the repository costs one removal command in the cache Valkey.
- Rows: no row changes. A row gets None or the error of a missing issue for such an item, as it does for a deleted issue today, and the later rounds of its lane do not list the item.
- Operation: the name of a store must be the name that GitHub gives for the repository now. After a rename of a repository, GitHub answers a read under the old name with the new name, and the store takes no such answer.
- Deleted internal code: none.

## Feasibility

- The defect is in the source at the base commit `9a65c7774`. In `src/devops_cli/roadmap/stores/github_store.py`, `issue`, `_require_issue` and `pull_title` validate the answer of `_read_or_none` with `_ISSUE` and use it with no comparison, and `_IssuePayload.record` takes `number` from the answer. `_revalidate_issue` does the same for the answer of a conditional read.
- GitHub documents the redirect. The REST reference of "Get an issue" (`docs.github.com/en/rest/issues/issues#get-an-issue`) says: "The API returns a `301 Moved Permanently` status if the issue was transferred to another repository." The store reads through `gh api`, which follows the redirect, so the store gets status 200 and the payload of the issue at its new place.
- The new tests fail on the base: `uv run pytest -n 4 tests/roadmap/stores/test_roadmap_github_store_issue_answer.py tests/roadmap/test_roadmap_rows_issue_answer.py` gave 24 failed and 6 passed with the source of `9a65c7774`. The 6 that pass are the 5 cases of an answer for the requested issue and the case of a 304 answer, which must read as before.
- The payload shapes of the project give the fields of the comparison. A recorded issue of `tests/fixtures/roadmap/issues-open.json` holds `url` and `html_url` and no `repository_url`. `GitHubFake.seed_issue` (`tests/support/fakes/github_repository.py`) gives `html_url` and `repository_url`. The number in a URL field is not compared: `issue_payload` of `tests/support/roadmap_github_store.py` gives the recorded issue #917 under another `number`.
- The numbers that left can live in the listing object. `service_jobs` (`src/devops_cli/roadmap/run.py`) builds one `IncrementalListing` for each lane and gives it to each round of that lane, and `IncrementalListing.read` runs one time for each store.
- The set that the claim covers is the places of `github_store.py` that validate an answer with `_ISSUE`. `git grep -n "_ISSUE\b" -- src/devops_cli/roadmap/stores/github_store.py` gives 7 lines after the change: the definition, the 3 places that take the answer of a request of a number (`_read_issue`, the conditional read of `_revalidate_issue` and the `PATCH` answer of `_send_edit`), the 2 listings (`_read_issues` and `newest_issue_number`) and `create_issue`. Each of the 3 places passes its answer to `_answered`. A listing and `create_issue` request no number.

## Existing Tool Considered

The need is a comparison of two fields of a GitHub answer with the request. No library holds this rule of the store. The standard library parses the URL fields (`urllib.parse.urlsplit` and `pathlib.PurePosixPath`, as `_is_pull_request_url` of the same module does), and `RepoRef` of this project (`src/devops_cli/github/repo_ref.py`) compares the names. The change builds no parser of its own. Cost to build: about 100 lines of source and 2 test modules, about 150 thousand tokens and 3 hours. The change deletes no internal code.

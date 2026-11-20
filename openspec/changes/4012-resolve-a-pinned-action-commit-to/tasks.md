# Tasks

## 1. Keep the pinned commit of an Action in the inventory

Kind: behavior. Reads: `src/devops_cli/research/models.py`, `src/devops_cli/research/workflow_pins.py`, `tests/research/test_inventory.py`, `tests/fixtures/research/repo/.github/workflows/ci.yml`, `tests/fixtures/research/repo/.github/actions/setup/action.yml`, `tests/research/test_advisories.py`, `tests/research/test_inventory_repository.py`, `tests/research/test_research_watch_file.py`, `tests/research/test_sweep.py`, `tests/research/test_watch_list.py`, `tests/research/test_mapping.py`. Changes: `src/devops_cli/research/models.py`, `src/devops_cli/research/workflow_pins.py`, `tests/research/test_inventory.py`.
Adds: `_COMMIT_LENGTH`, `_commit_ref`

- [x] 1.1 `test_inventory_lists_one_component_for_each_pin_of_the_fixture_repository` in `tests/research/test_inventory.py`: the `actions/checkout` component at line 7 of `tests/fixtures/research/repo/.github/workflows/ci.yml` holds the commit `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` beside the version `v7`, and each other Action pin of that fixture holds its own commit
  - Verification: `$ uv run devops ci test tests/research/test_inventory.py` fails on the base
- [x] 1.2 Add `commit: str = ""` to `src/devops_cli/research/models.py:class Component` and state it in the docstring beside `version`. Add the module constant `_COMMIT_LENGTH = 40` and the helper `_commit_ref(ref)` to `src/devops_cli/research/workflow_pins.py:def _component`, where `_commit_ref` gives the ref when it is 40 hexadecimal characters and an empty string otherwise, and pass `commit=_commit_ref(ref)` beside `version=comment or ref,`. Give `_component` of `tests/research/test_inventory.py` a `commit` parameter with the empty string as default, and give each expected Action component its commit: `actions/checkout` at line 7 of `tests/fixtures/research/repo/.github/workflows/ci.yml` gets `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`, the two `astral-sh/setup-uv` pins at lines 8 and 13 get `bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb` and `cccccccccccccccccccccccccccccccccccccccc`, `actions/cache` at `tests/fixtures/research/repo/.github/actions/setup/action.yml` gets `dddddddddddddddddddddddddddddddddddddddd`, and `example-org/no-comment` at line 15 keeps the empty string
  - Verification: `$ uv run devops ci test tests/research/test_inventory.py` passes

## 2. Select the highest full release tag of a commit

Kind: behavior. Reads: `src/devops_cli/research/version_match.py`, `tests/research/test_version_match.py`. Changes: `src/devops_cli/research/version_match.py`, `tests/research/test_version_match.py`.
Adds: `full_release`, `release_for_commit`

- [x] 2.1 `test_the_highest_full_release_tag_of_the_commit_is_the_release` in `tests/research/test_version_match.py`, which covers the scenario `The highest release of the commit wins` of the requirement `A pinned commit takes the highest full release of its tags`
  - Verification: `$ uv run devops ci test tests/research/test_version_match.py` fails on the base
- [x] 2.2 Add `full_release(text)` to `src/devops_cli/research/version_match.py:def pinned_version`: it gives the `Version` of a tag that holds three release numbers and no prerelease, dev, local or post part, and None otherwise. Add `release_for_commit(tags, commit)`: it takes pairs of tag name and commit sha and gives the name of the highest full release tag whose sha equals `commit`, and None when no tag does. Cover a major tag, a prerelease tag, two releases at one commit and a tag at another commit in `tests/research/test_version_match.py`
  - Verification: `$ uv run devops ci test tests/research/test_version_match.py` passes

## 3. Read the tags of an Action repository

Kind: behavior. Reads: `src/devops_cli/research/github_advisories.py`, `tests/research/test_github_advisories.py`, `src/devops_cli/http/public_api.py`, `tests/fixtures/research/advisories/github/advisories_actions.json`, `tests/http/test_http_egress.py`, `tests/research/test_advisories.py`, `tests/security/test_vulnerability_lookup.py`, `tests/support/fakes/http.py`. Changes: `src/devops_cli/research/github_advisories.py`, `tests/research/test_github_advisories.py`.
Adds: `GhsaTag`, `GhsaTagCommit`, `GhsaTagLookup`, `tags_of`, `_read_tag_pages`

- [x] 3.1 `test_the_tags_of_a_repository_are_read_page_by_page_until_the_commit` in `tests/research/test_github_advisories.py`, which covers the scenario `The commit is on a later page` of the requirement `The tags of an Action are read page by page`
  - Verification: `$ uv run devops ci test tests/research/test_github_advisories.py` fails on the base
- [x] 3.2 Add `GhsaTagCommit` with `sha`, `GhsaTag` with `name` and `commit`, and `GhsaTagLookup` with `status`, `reason` and `tags` to `src/devops_cli/research/github_advisories.py:class GitHubAdvisoryClient`, beside `GhsaLookup`, each with `extra="ignore"` and no default for the fields that the endpoint always sends. Add the method `tags_of(repository, commits)` and its helper `_read_tag_pages(url, commits)`: it reads `GET /repos/{owner}/{repo}/tags?per_page=100` page by page with the host rule, the page bound and the byte cap of `src/devops_cli/research/github_advisories.py:def _read_pages`, stops when every sha of `commits` is found or the reply names no next page, and returns a failed lookup with the reason when a read fails or the list passes the page bound. Test it in `tests/research/test_github_advisories.py` with the fake transport of `tests/support/fakes/http.py`: a commit on the second page, a tag that is no full release, and a 500
  - Verification: `$ uv run devops ci test tests/research/test_github_advisories.py` passes

## 4. Resolve a pinned commit before the advisory match

Kind: behavior. Reads: `src/devops_cli/research/advisories.py`, `src/devops_cli/research/github_advisories.py`, `src/devops_cli/research/version_match.py`, `tests/research/test_advisories.py`, `tests/research/github_recording.py`, `tests/fixtures/research/advisories/github_repo/.github/workflows/ci.yml`, `tests/commands/test_research_advisories.py`. Changes: `src/devops_cli/research/advisories.py`, `tests/research/test_advisories.py`, `tests/research/github_recording.py`, `tests/fixtures/research/advisories/github/tags_actions_checkout.json` (new).
Adds: `action_commit_repositories`, `resolve_action_commits`

- [ ] 4.1 `test_a_pinned_commit_resolves_to_its_full_release` in `tests/research/test_advisories.py` gives `v4.2.2` for the `actions/checkout` pin at line 7 of `tests/fixtures/research/advisories/github_repo/.github/workflows/ci.yml`; `test_a_pinned_commit_with_no_full_release_tag_stays_unpinned` and `test_a_failed_tags_read_is_a_failure_and_not_a_clean_pin` cover the other two cases of the issue; and `test_the_requests_of_a_run_with_actions_and_a_watch_list_name_each_repository` covers the scenario `The plan of a dry run` of the requirement `The tags of one Action repository are read once in a run`
  - Verification: `$ uv run devops ci test tests/research/test_advisories.py` fails on the base
- [ ] 4.2 Add `action_commit_repositories(inventory)` and `resolve_action_commits(inventory, github)` to `src/devops_cli/research/advisories.py:def find_advisories`: the first gives the Action repository of each pin that holds a commit and a version that names no full release, with its commits, and skips a name with no `/`; the second reads the tags of each such repository once with `tags_of`, replaces the version of each pin with `release_for_commit`, and gives one `LookupFailure` for each pin of a repository whose read failed, with the repository as the name and the pin version and the reason. Call it at the start of `find_advisories` and add its failures to the report, and list one `PlannedRequest` for the tags of these repositories, with the target `https://api.github.com/repos/<owner>/<repo>/tags` and the repeat `for each action repository with a commit pin`, at the head of `advisory_requests`. Serve the new recording in `serve_recorded_github` of `tests/research/github_recording.py` for the tags path of `actions/checkout` and an empty list for any other tags path, then update `tests/research/test_advisories.py`: the OSV batch becomes `web.recorded[1]` and the host list gains the tags request in `test_only_registry_packages_are_asked_and_the_rest_is_counted`, `queried` becomes 4 and `unpinned` becomes 0 in the summary of `test_a_github_advisory_of_an_action_gives_a_finding_where_osv_gives_none`, `queried` becomes 3 in `test_a_component_that_the_watch_list_does_not_map_is_counted_as_not_covered`, the planned request list takes the tags entry in `test_the_requests_of_a_run_with_actions_and_a_watch_list_name_each_repository`, and the two tests that build their own transport serve an empty tags list, `test_a_github_read_that_fails_is_reported_for_its_component_and_is_not_clean` and `test_an_advisory_with_a_range_that_cannot_be_read_is_a_failure_that_names_it`. Record the measured number of tags requests of `uv run devops research advisories --dry-run` on this repository in the pull request, against the limit of 60 requests an hour without a token
  - Verification: `$ uv run devops ci test tests/research/test_advisories.py` passes

## Criteria

- Group 1: The inventory keeps the pinned commit of an Action beside its version.
- Group 4: For a pin with a commit and a version that is not a full release, the command reads the tags of the Action's repository (`GET /repos/{owner}/{repo}/tags`, `api.github.com`, already approved as an egress destination) and takes the highest full release tag that points to the commit.
- Group 4: Tests with recorded responses: a commit with a full release tag gives that release; a commit with none stays `unpinned`; a failed read is a failure and not a clean pin.
- Group 4: The number of extra requests for this repository is stated in the pull request, against the limit of 60 requests an hour without a token.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

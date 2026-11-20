# Proposal

## Why

An Action that a workflow pins to a commit and a major tag (`uses: <action>@<commit> # v7`) names no one release, so `devops research advisories` counts the pin in `unpinned` and matches no advisory to it (#4012). A range such as `< 7.5` or `>= 7.2` needs the exact release of the commit. The issue reports 47 of 80 Action pins of this repository pinned that way; no tool of this run counted them.

## What Changes

- `src/devops_cli/research/models.py:class Component` gains `commit: str = ""`, so the inventory keeps the pinned commit of an Action beside its version.
- `src/devops_cli/research/workflow_pins.py:def _component` fills that field from the ref of a `uses:` line when the ref is 40 hexadecimal characters, and leaves it empty otherwise.
- `src/devops_cli/research/version_match.py:def pinned_version` gains the neighbours `full_release` and `release_for_commit`, which pick the highest full release tag that points at a commit.
- `src/devops_cli/research/github_advisories.py:class GitHubAdvisoryClient` gains `tags_of`, which reads `GET /repos/{owner}/{repo}/tags` page by page on `api.github.com` until each pinned commit is found, under the page bound `DEFAULT_GITHUB_ADVISORIES_MAX_PAGES` of 10 and the byte cap `DEFAULT_GITHUB_ADVISORIES_MAX_RESPONSE_BYTES` of 4 MiB.
- `src/devops_cli/research/advisories.py:def find_advisories` resolves each Action commit pin through the tags before it plans the advisory reads, and `def advisory_requests` lists one tags request for each Action repository that holds a commit pin.
- A pin whose commit has no full release tag stays in `unpinned`, and a failed tags read adds a `LookupFailure` that names the Action repository and makes the command exit 1.
- The tests read the recorded answer `tests/fixtures/research/advisories/github/tags_actions_checkout.json` and assert the three cases of the issue: a full release tag at the commit, no full release tag at it, and a failed read.
- The spec deltas of `research-advisories`, `research-inventory` and `public-api-egress` state the commit field, the resolution rule, the failure and the tags endpoint on the approved host.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `research-advisories`: A pinned commit takes the highest full release of its tags, The tags of an Action are read page by page, A commit with no full release stays unpinned, A failed tags read is a failure and not a clean pin, The tags of one Action repository are read once in a run, Each GitHub Action with an exact release is checked against the GitHub advisories
- `research-inventory`: An Action pin to a commit keeps its commit (added; the requirement "The inventory lists each pin as a typed component" stays as it was)
- `public-api-egress`: The tags read of a pinned Action goes to api.github.com only (added; the owner approval of 2026-11-07 stays as recorded)

## Impact

- Code: `src/devops_cli/research/models.py`, `src/devops_cli/research/workflow_pins.py`, `src/devops_cli/research/version_match.py`, `src/devops_cli/research/github_advisories.py`, `src/devops_cli/research/advisories.py`
- Tests: `tests/research/test_inventory.py`, `tests/research/test_version_match.py`, `tests/research/test_github_advisories.py`, `tests/research/test_advisories.py`, `tests/research/github_recording.py`, `tests/fixtures/research/advisories/github/tags_actions_checkout.json`

## Feasibility

- The probes confirm that the cited host and field are no paths of the tree: "The path `api.github.com` is no file of the staging commit. No commit in the history deleted or renamed it." and "The path `commit.sha` is no file of the staging commit. No commit in the history deleted or renamed it."
- `src/devops_cli/commands/research.py:129:`report = find_advisories(`` is the one call site of the resolution, in the command that builds the GitHub client.
- The premise holds in the pin reader: `src/devops_cli/research/workflow_pins.py:42:`name, _, ref = uses.partition("@")`` keeps the ref, and `src/devops_cli/research/workflow_pins.py:47:`version=comment or ref,`` replaces it with the comment, so the commit is dropped today.
- `src/devops_cli/research/version_match.py:30:`return version if len(version.release) >= _RELEASE_PARTS else None`` gives None for `v7`, so `src/devops_cli/research/advisories.py:def _plan` counts that pin in `unpinned` instead of asking GitHub about it.
- The pin record holds no commit field today: `src/devops_cli/research/models.py:class Component` lists `version` and no commit.
- The review findings of the earlier reply are fixed at their place: group 1 now reads `tests/research/test_mapping.py` and no file with a space in its name, group 3 reads `tests/support/fakes/http.py`, and group 4 names the file `tests/fixtures/research/advisories/github_repo/.github/workflows/ci.yml` in its test.
- Group 1 names the existing test `test_inventory_lists_one_component_for_each_pin_of_the_fixture_repository` at `tests/research/test_inventory.py:124`, and the commit and version that it asserts are those of `tests/fixtures/research/repo/.github/workflows/ci.yml:7:`- uses: actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa # v7``.
- Group 1 gives every Action pin of the same fixture its commit: `tests/fixtures/research/repo/.github/workflows/ci.yml:8:`- uses: astral-sh/setup-uv@bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb # v10.2.0``, `tests/fixtures/research/repo/.github/workflows/ci.yml:13:`- uses: astral-sh/setup-uv@cccccccccccccccccccccccccccccccccccccccc # v10.0.1`` and `tests/fixtures/research/repo/.github/actions/setup/action.yml:5:`- uses: actions/cache@dddddddddddddddddddddddddddddddddddddddd # v6.1.0``, and leaves the empty string on the pin whose ref is no commit.
- Group 4 changes the test that reads the first recorded request, `tests/research/test_advisories.py:120:`for query in web.recorded[0].json["queries"]``, and the two tests that build their own transport, `tests/research/test_advisories.py:396:`web.respond("GET", QDRANT_URL + "?per_page=100", 500, {})`` and `tests/research/test_advisories.py:426:`if request.url.path.startswith("/repos/")``, so that each of them serves a tags answer.
- The host is the one that the client reads: `src/devops_cli/research/github_advisories.py:106:`BASE_URL = "https://api.github.com"``, and `src/devops_cli/research/github_advisories.py:def _read_pages` follows a next page only on that host.
- The page bound and the byte cap that the tags read reuses: `src/devops_cli/config/defaults.py:323:`DEFAULT_GITHUB_ADVISORIES_MAX_PAGES: int = 10`` and `src/devops_cli/config/defaults.py:318:`DEFAULT_GITHUB_ADVISORIES_MAX_RESPONSE_BYTES: int = 4 * 1024 * 1024 # 4 MiB``.
- `read_inventory` needs a checkout of the repository: the command gives it the root of the current folder, and a test gives it the fixture folder of `tests/fixtures/research/advisories/github_repo/.github/workflows/ci.yml`.
- `tags_of` needs a client of `api.github.com` and a network: the command builds the client with the optional token, and a test hands it the fake transport of `tests/support/fakes/http.py`.
- `resolve_action_commits` needs that same client and network, and `find_advisories` needs the clients of OSV, GitHub and CISA KEV and the network that they use: a test passes the fake transport, and a run of the command uses the real clients.
- #3987 is delivered: its client is at the staged commit, `src/devops_cli/research/github_advisories.py:class GitHubAdvisoryClient`, and its comment of 2026-11-07 records the owner's approval of the egress to that host.
- The verify commands are `uv run devops ci test <module>` of the runner image, so each group needs the failure class `test` and none of `NOT_IN_RUNNER`; the pod setting `readOnlyRootFilesystem: true` holds because the tests write only under `tmp_path`, with `runAsNonRoot: true` and all capabilities dropped.
- No tool of this run counted the Action pins of the issue, so the plan makes no claim over that set: group 4 runs `uv run devops research advisories --dry-run` on this repository and states the measured number of tags requests in the pull request, against the limit of 60 requests an hour without a token.

## Existing Tool Considered

The GitHub REST API `GET /repos/{owner}/{repo}/tags`, through the client that `src/devops_cli/research/github_advisories.py` already builds for `api.github.com`. `zizmorcore/zizmor` (MIT, maintained, last activity 2026-11-09) covers the audit only as a standalone scanner and feeds no advisory into the research inventory, as the alternatives check of 2026-11-10 recorded with the verdict `partly`. No new scanner is built.

## Dependencies

- #3987: the tags read goes through the GitHub advisories client that #3987 delivered; its comment of 2026-11-07 records the owner's approval of the egress to `api.github.com` for the advisories API. The tags path `GET /repos/{owner}/{repo}/tags` is new on that host, and the pull request asks the owner to approve it. The client is at the staged commit, so no work of it is left.

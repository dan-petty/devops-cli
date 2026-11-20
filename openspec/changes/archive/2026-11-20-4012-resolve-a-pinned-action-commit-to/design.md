# Design

## Decisions

- **Read the tags through `GET /repos/{owner}/{repo}/tags` on `api.github.com`, with the client of #3987.**: The endpoint returns each tag name with its commit sha, and the host is already an approved egress destination of the research agent.
- **Take the highest full release tag whose commit sha equals the pinned commit, and ignore major-only tags, prerelease tags and tags with a post or local part.**: A full release gives the exact version that an advisory range needs, and semver gives a total order over the tags.
- **Add an optional `commit` field to `src/devops_cli/research/models.py:class Component` and fill it from the ref of the workflow pin.**: The pin line holds the commit and the parser drops it; one field keeps the existing pins valid and needs no second structure.
- **Resolve the inventory into a second inventory before `_plan`, so a resolved pin is planned at its release and an unresolved one is counted in `unpinned`.**: One pure function over the components keeps the plan, the queried count and the `unpinned` count consistent, and the advisory match stays unchanged.
- **Read the tags once for each distinct Action repository in a run, page only until every pinned commit of that repository is found, and treat a list longer than `DEFAULT_GITHUB_ADVISORIES_MAX_PAGES` of 10 pages as a failed read.**: One request for each pin can pass the limit of 60 requests an hour that a caller with no token has, and a commit past the page bound leaves the release unknown, so a clean pin would be false.
- **Fail the command with one failure for each pin of the repository when the tags read fails, naming the repository, the pin version and the reason.**: A failed read leaves the release unknown, so a clean pin would be false, and the pin's own version keeps the printed line readable.
- **Skip a name with no `/` when the tags are grouped, and count its pin in `unpinned`.**: The tags URL needs `owner/repo`, so a name without a slash names no repository to read.
- **Replace the version of the pin with the release that the tags give, before the existing advisory match.**: It reuses `_github_matches` and the range logic of `packaging` unchanged.
- **Use recorded GitHub answers in `tests/research/test_advisories.py` and `tests/research/test_github_advisories.py`.**: The existing advisory tests need no network and no token, and a recorded answer checks the HTTP shape as well as the selection.
- **State the measured tags request count in the pull request: the number of repositories that `action_commit_repositories` gives for this repository, and the tags page of each pinned commit.**: The dry run lists the tags request once with a repeat, so it gives no count. On 2026-11-20 the count is 2 repositories with each commit on the first page, so a run sends 2 extra requests.
- **Group the tags reads by `owner/repo`, the first two parts of the Action name, and keep the full name for the release and the advisory match.**: An Action in a sub-path of its repository, such as `github/codeql-action/init`, has no tags route of its own, and GitHub answers 404 for `/repos/github/codeql-action/init/tags`.
- **Give one failure for each repository and version of a failed tags read.**: `LookupFailure` holds no file and no line, so one failure for each pin repeats one line, and the existing reads give one failure for each pin group.
- **Extend the existing research advisories path and build no new scanner.**: The advisory match, the client and the report already exist, so a second scanner would duplicate them and add maintenance cost.

## Rejected alternatives

- **GitHub GraphQL refs query for the tags.**: It needs a new query shape and gives no simpler tag-to-commit read than the REST list.
- **Git `ls-remote` for the tags.**: It needs a separate transport and a separate token path from the client of #3987.
- **Take the first tag that points at the commit.**: The tag order is not semantic, so the first match can be an older release than a later one.
- **Take the major tag as the release.**: A major tag names no one release and cannot match a range such as `< 7.5`.
- **Accept a prerelease tag as the release.**: A prerelease is no full release and can give a version that no user runs.
- **Keep a separate map of commit to repository.**: It adds a second structure that has to stay in step with the inventory.
- **Parse the commit again where the match runs.**: It repeats the workflow parsing and breaks the contract of the inventory.
- **Resolve the pins inside `_plan` and read the tags after the OSV batch.**: It splits the resolution between the plan and the read and needs a second plan pass, while the inventory rewrite keeps one pure function and one read.
- **Send one tags request for each pin.**: The pins of one repository can pass the limit of 60 requests an hour.
- **Read all tags of all Actions before any match.**: It wastes requests on repositories whose pins already name a full release.
- **Treat a pin whose tags read failed as unpinned and nothing else.**: It hides an operational failure and checks no advisory, which is no verdict.
- **Retry a failed tags read without a limit.**: It can pass the rate limit and delay the command.
- **Teach the advisory matcher about commits.**: It puts knowledge of the GitHub API in the matcher and repeats the resolution.
- **Match the pin to its major version only.**: It cannot answer a range such as `>= 7.2` or `< 7.5`.
- **Read the tags from live GitHub calls in the tests.**: They need a token and a network, and they are not deterministic.
- **Mock only the client method in the tests.**: Such a test passes without checking the shape of the HTTP answer.
- **Read only the first tags page.**: A repository with many tags can hold the pinned commit on a later page.
- **Read every tags page on each run.**: It wastes requests after the command finds the commit.
- **Add a new scanner for Actions.**: It duplicates the advisory path and adds maintenance cost.

## Security

A read of `api.github.com` crosses the trust boundary of the research agent, because it sends the optional GitHub token to that host and reads a body that it does not control. A person must confirm that the tags endpoint stays on the approved egress list of the `public-api-egress` spec, that no other host is read, and that a reply over the byte cap or a next page on another host is a failed read. `tests/research/test_github_advisories.py` fails if the client follows a next page on another host, and `tests/research/test_advisories.py` fails if a failed tags read becomes a clean pin. The tests send no request and need no token.

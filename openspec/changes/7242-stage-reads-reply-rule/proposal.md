# Proposal: #7242

## Why

Issue #7242: `docs/roadmap/stage.md` (section "The comments of the item") and `SECURITY.md` (item 14) say that a roadmap job gives its model only the comments of a person with write access and of the Service App. Refine, the alternatives job and the first request of the stage job keep this rule with `trust.trusted_replies`. The other reads of the stage job did not keep it. The tools `read_issue` and `find_issues`, the overlap list, the titles of the declared dependencies, the issue listing and the GitHub read snapshot of `prepare` gave the text of each author. The repository is public, so each account can open an issue or a pull request and write a comment.

## What Changes

- `read_issue` and the file `work/github/issues/<number>.json` give the title, the body and the comments only for an item whose author `trust.is_trusted` accepts. They give only the last 3 comments that `trust.trusted_replies` keeps, and the filter runs before the cut. For an item of another account they give the number, the state, the labels, the closing pull request and one fixed line, and they do not read the comments.
- One fixed text stands for the title of an item of another account in `find_issues`, in the overlap list of the request, in `work/github/pulls.json`, in `issue_dependencies` and in the issue listing of `prepare`.
- `work/github/issue-index.jsonl` has a line only for an open issue of a trusted author.
- `work/github/pull-files/<number>.json` holds the patch text only for a pull request of a trusted author. A pull request of another account, or one whose author `prepare` could not read, keeps the name and the status of each changed file.
- `GitHubClient.get_last_comments` returns each comment with the relation and the login of its author. `IssueView` and `OpenItem` hold the same two fields. The GraphQL read of the open pull requests asks for the author in the same request.
- `trust.is_trusted` and `trust.trusted_replies` take each record that holds the relation and the login of an author.
- `docs/roadmap/stage.md` gets the section "The text of other items".
- These reads are behavior that the planner and the agent observe, so the change carries a delta for three capabilities. It fits in one pull request.

## Capabilities

### Modified Capabilities
- `roadmap-stage/toolbox`: `read_issue` and `find_issues` give the text of trusted authors only.
- `roadmap-stage/phases`: the issue files, `pulls.json`, the pull request files, the issue index and the issue listing of `prepare` give the text of trusted authors only.
- `roadmap-stage/context`: the overlap list and `issue_dependencies` give the title of an item of a trusted author only.

## Impact

- The planner and the agent of the stage Job read the title, the body, the comments and the patch text of a person with write access, of the Service App's bot and of `github-actions[bot]`. For each other account, a bot of dependency updates included, they read the number, the state, the labels, the plan mark and the file names.
- The count of GitHub requests does not rise. The read of an item of another account makes one request fewer, because it does not read the comments.
- A test that gives these reads an issue, a comment or a pull request names the author in its data.

## Feasibility

Confirmed in the worktree of the change:
- `git grep -n "get_last_comments" -- src` on the base shows two callers, both in `src/devops_cli/roadmap/stage/`, so the new return type changes no other reader.
- `git grep -n "\.title" -- src/devops_cli/roadmap/stage` shows 84 lines. Four places gave only the title of another item: `stage_overlap.py` (`_open_pull`, which also feeds `pulls.json`), `stage_github.py` (`_found_line`), `stage.py` (`dependency_title`) and `stage_job_phases.py` (`issue_listing`). Each now applies `trust.is_trusted`. The other lines hold the title of the staged item, which the rule `_author` of `stage.py` admits only for a trusted author, the title of a task group of the plan, or text for a person. The titles of web search results in `stage_tools.py` are no GitHub item and stay as they are.
- The new tests fail on the base: `uv run devops ci fail-to-pass --base origin/main` names them.
- A read of the GitHub API on 2026-11-25 gave the author of a pull request of an App as `{"__typename":"Bot","login":"<slug>"}` from GraphQL and as `<slug>[bot]` from REST. So the listing adds `[bot]` to the login of an author of the type `Bot` before it compares it with `trust.bot_logins`.

## Existing Tool Considered

No open tool decides which GitHub authors the jobs of this project trust. The rule is in `src/devops_cli/roadmap/trust.py`, and the change uses `is_trusted` and `trusted_replies` of that module again, with no second rule. GitHub gives `author_association` and the type of the author in the REST and GraphQL answers that the job reads already, so the change needs no library and no new request. The change deletes the private model `_CommentText` of `src/devops_cli/github/client.py`, which `CommentView` replaces.

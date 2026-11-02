# Proposal

## Why

Issue #3238: the reviews of the plans staged after the gates merged show two defects that the nine tools of the stage planner cannot catch. Both gave a blocker in every case.

1. A rename or a removal misses references. The plan of #3228 named 4 of the 11 files that hold `intake-eval`. It missed six calls in `tests/roadmap/test_roadmap_duplicate_eval.py` and five requirements in `openspec/specs/roadmap-intake-duplicates/spec.md`. `search_code` cuts its answer by characters and has no summary by file, so a file at the end of the answer is lost.
2. A dependency, a park or an overlap is not seen. The plan of #3225 says "Dependencies: None" while open #3207 parks #3060. The plan of #3234 does not name open #2740, which chose the same redaction point. The planner has no tool that reads an issue or a pull request.

## What Changes

- `StageTools` gets three read-only tools. `references(name)` lists every file of the staged commit that holds a text, with the exact count of lines in the file, at most 60 files, taken in turn from the source, the tests, the specs, the documents and the other files. `read_issue(number)` reads one issue or pull request of the repository on GitHub. `find_issues(terms)` lists the open issues and pull requests that name the terms, at most 10, each as `#N state title`.
- `read_issue` and `find_issues` use the GitHub client of the Service (`get_github_session().client`) and its existing App token. They send GET requests to the GitHub API host only. They add no permission and no host. `GitHubClient` gets four read-only methods for them: `get_issue`, `get_last_comments`, `get_closing_pull` and `search_open_items`.
- The text from GitHub is data. The tool masks secrets with `mask_secrets`, cuts each text, and puts a line in the answer that says it is no instruction. Each failure is an answer as text: no such item, the rate limit, no connection, no client.
- The setting `roadmap.stage.toolset` has the values `base` (the nine tools of today, no GitHub tool) and `extended` (base plus the three). The default is `extended`. It has the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET`, and `k8s/devops/configmap.example.yaml` sets it.
- The prompt `roadmap_stage_tools_extended.md` says when to call each tool. The prompt `roadmap_stage_tools.md` stays the prompt of `base` and no longer says that no tool opens a network connection.
- The golden-set run (`devops roadmap eval stage`) has no GitHub client. Its GitHub tools answer that GitHub is not available, because GitHub holds the state of today and not the state of the staging commit of a case.
- Observable behavior changes (a setting, a variable, tools and a prompt), so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-stage`: the toolbox, the toolset setting, `references`, the two GitHub reads and the prompt of the extra tools.

## Impact

- Code: `src/devops_cli/github/client.py`, `src/devops_cli/roadmap/stage_tools.py`, `stage_toolbox.py`, `stage.py`, `refine_investigation.py` (one public name for the exit code of a timed-out git command), the new `stage_github.py` and `stage_references.py`, `src/devops_cli/config/constants.py`, `defaults.py` and `settings.py`.
- Prompts: `src/devops_cli/ai/tasks/roadmap_stage_tools.md` and the new `roadmap_stage_tools_extended.md`.
- Documents: `docs/roadmap/stage.md`, `k8s/README.md`, `CONTEXT.md`, and the generated `docs/CONFIGURATION.md` and `docs/ENV_VARS.md`. `k8s/devops/configmap.example.yaml` sets `toolset`.
- Tests: `tests/roadmap/test_roadmap_stage_tools.py`, `test_roadmap_stage_toolbox.py`, `test_roadmap_stage_settings.py`, `test_roadmap_stage_plan.py`, `test_roadmap_limit_classes.py`, and the new `tests/roadmap/test_roadmap_stage_github.py` and `tests/github/test_github_client_issue_reads.py`.
- Security: the planner had no network. With `extended` it reads GitHub with the token of the Service. A person must confirm this before merge. The setting `toolset: base` removes the read.

## Feasibility

- The premise of defect 1 holds on `origin/main`. `git grep -n -I -F -e intake-eval ff9ad065 --` finds 36 lines in 18 files. The tool `search_code("intake-eval")` on the same commit answers 26 lines in 14 files, cut at the 8000 characters of a tool answer. It leaves out `tests/ai/mcp/test_mcp.py`, `tests/fixtures/dry_run_gaps.json`, `tests/roadmap/test_roadmap_duplicate_eval.py` and `tests/roadmap/test_roadmap_intake.py`. The caps of #3206 are higher than the caps the issue names (240 lines, 241 matches for a file), so the loss now comes from the cut of the answer and not from a cap for a file. The new tool answers the same search in 19 lines and 1215 characters, with all 18 files.
- The GitHub API gives what `read_issue` needs. `gh api repos/dan-petty/devops-cli/issues/3231` returns `state`, `title`, `comments` and, for a pull request, `pull_request.merged_at` (`2026-11-02T16:51:14Z`). `gh api "repos/dan-petty/devops-cli/issues/3229/events?per_page=100"` returns a `closed` event with `commit_id` `ff9ad065ae72bdd28279026efb070dc310510fb5`, the merge commit of #3231. `GitHubClient.get_commit_pulls` already maps a commit to its pull requests with `merged_at`. So an issue closed by a pull request shows the merged pull request with no new endpoint.
- The search for open items is `GET /search/issues?q=<terms> repo:<repo> is:open`. A qualifier in the terms, such as `repo:other/private`, would widen the search to another repository that the App can read. The client takes every colon and quote out of the terms first, and a test holds it.
- The tools of pydantic-ai (`Tool(method, takes_ctx=False)`) take the arguments `number: int` and `terms: str` from the signature, as the other tools take theirs. A test runs a toolbox run with the three tools and a scripted model.
- `git grep -n -I -F -e <name> <sha> --` with no `--max-count` has no cap for a file. On `load_settings` it returns 786 lines in 233 files in less than the 15 s timeout of `_git`.

## Existing Tool Considered

`git grep` (the tool that `search_code`, `callers` and now `references` call) and the GitHub client of the project (`GitHubSession`, `GitHubClient`) cover the need. No new library is added. The GitHub MCP server and `gh` cover the same reads for a person, but the Service runs without them, and rule 7 of AGENTS.md sends GitHub reads through the client that paces its requests. The change builds about 400 lines of source and 600 lines of tests: roughly 120000 tokens to build and to fix, 8000 tokens a year to keep, and about 5 hours. The change deletes no code: it adds a public name for the exit code of a timed-out git command (`GIT_TIMED_OUT`, was `_TIMED_OUT`).

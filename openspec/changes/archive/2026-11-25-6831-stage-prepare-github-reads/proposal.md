# Proposal: #6831

## Why

The separate agent phase runs stock `Coder` with no GitHub credential and no `read_issue` or `find_issues` tool (`src/devops_cli/roadmap/stage/stage_agent.py`, `src/devops_cli/roadmap/stage/stage_job_phases.py`). Plans written without those GitHub reads miss related issues, reviewer comments, open pull request overlaps, and changed pull request files. Meanwhile `--phase prepare` already holds the Service App token and prepares `work/`.

## What Changes

- Extend `GitHubClient` (`src/devops_cli/github/client.py`) with `PullRequestFilePatch`, `get_pull_files`, and bounded `list_open_issues` for up to 1000 open issues.
- Add `src/devops_cli/roadmap/stage/stage_github_snapshot.py` so `--phase prepare` writes the GitHub snapshot under `work/github/`:
  - `work/github/issues/<number>.json`: each issue or pull request named as `#<number>` in the item body, with state, title, labels, bounded secret-masked body, last comments, and closing pull request when closed.
  - `work/github/pulls.json`: open pull requests with `number`, masked `title`, `state`, and changed file paths (`stage_overlap.open_pulls`).
  - `work/github/pull-files/<number>.json`: changed file paths and bounded masked `patch` diffs for each pull request named by the item body.
  - `work/github/issue-index.jsonl`: newline-delimited open issues (at most 1000 lines, body cut to 500 characters, total at most 1 MiB) including `"ref": "#<number>"` for shell search (`grep`/`rg`).
  - `work/github/errors.json`: records any failed GitHub read without aborting `prepare`.
- Pass the snapshot folder path in `_request` (`src/devops_cli/roadmap/stage/stage_job_phases.py`) and update `src/devops_cli/ai/tasks/roadmap_stage_coder.md` to name the four snapshot paths and shell search command.
- Update `docs/roadmap/stage.md` so the `--phase prepare` description names `work/github/`.
- Keep `--phase agent` on stock `Coder` tools only and keep `--phase all` on live GitHub reads without writing `work/github/`.

## Capabilities

- Modifies `roadmap-stage/phases` to write the `work/github/` snapshot in `prepare`, document the snapshot in `roadmap_stage_coder.md`, preserve stock `Coder` tools in `agent`, and preserve live reads with no `work/github/` output in `all`.

## Impact

- Callers of `--phase prepare` write additional read-only JSON/JSONL files under `work/github/` (`0o600` files in `0o700` dirs) and count those fetches in the request budget of `prepare`.
- Stock `Coder` in `--phase agent` inspects related issues, open PR paths, PR file patches, and up to 1000 open issues via shell commands without any GitHub credential.
- This change fits in one pull request and deletes no internal code.

## Feasibility

- Confirmed against source on `origin/main`:
  - `src/devops_cli/roadmap/stage/stage_agent.py`: `build_stage_agent` uses `Coder(repo_context=False, sub_agents=False)` and `RequireVerification`, with no custom GitHub tools (`script.tools_offered == stock.tools_offered` in `tests/roadmap/stage/test_roadmap_stage_agent.py:104`).
  - `src/devops_cli/roadmap/stage/stage_job_phases.py`: `_Prepare.hand_on` (line 430) writes `work/issues.json` and `work/input.json`; `_request` (line 609) builds the JSON message for the agent.
  - `src/devops_cli/github/client.py`: `GitHubClient` has `get_issue` (line 824), `get_last_comments` (line 829), `get_closing_pull` (line 846), and `graphql` (line 920), while `PullRequestFile` (line 190) has no `patch` field (note `tests/fixtures/github/hello_world_pull_request.json` carries `patch` keys, so a dedicated `PullRequestFilePatch` keeps `PullRequestFile` equality intact for existing compare tests in `tests/github/test_github_client.py:169`).
  - `src/devops_cli/roadmap/stage/stage_overlap.py:157`: `open_pulls` already fetches open pull requests and changed file paths via GraphQL.
- First checks run against the real system / fake API: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prepare.py`, `tests/roadmap/stage/test_roadmap_stage_agent_phase.py`, `tests/roadmap/stage/test_roadmap_stage_github_snapshot.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, and `tests/github/test_github_client.py`.

## Existing Tool Considered

The alternatives check recorded on #6831 (2026-11-23, `in-use`) evaluated `cli/cli` (`github.com/cli/cli`, MIT, maintained). The repository already uses `cli/cli` and `GitHubSession`/`GitHubClient` for fetching issues, comments, pull requests, and files; it lacks an on-disk credential-free snapshot under `work/github/`, bounded JSONL search index, and Coder prompt instructions. Building the snapshot module, client helpers, prompt updates, and tests is ~300 lines (~55k tokens build, ~10k tokens/month maintenance, ~1 day).

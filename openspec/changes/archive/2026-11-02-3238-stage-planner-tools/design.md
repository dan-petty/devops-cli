# Design

## Decisions

- **The GitHub reads go through `GitHubClient`, as new read-only methods.** The stage job already uses `get_github_session().client` for its draft pull requests. `RoadmapStore` would need four new methods in its protocol and in the in-memory store, and it reads issues through `gh`. The client reads through the REST session of the process, with the App token of the Service, paced like the other requests. The four methods are `get_issue`, `get_last_comments`, `get_closing_pull` and `search_open_items`.
- **The tools get the client when they run.** `StageGitHub` holds the repository and a function that returns the client. A plan run that calls no GitHub tool never asks for a GitHub identity. A missing identity is an answer as text.
- **A failure of GitHub is text for every class.** `GitHubOperationError` covers the missing item, the rate limit, a refused token and a failed connection. The answer names the class and says to go on without the read. It never holds the message of the error, because that message can hold text that the network sent. A rejected token does not stop the run here, although the job stops on it elsewhere (`_STOP_THE_RUN`): a planner without GitHub still plans.
- **`references` counts with `git grep -n`, shows the counts and not the lines.** A rename needs the files and how many lines each holds. The model reads a file with `read_file` when it needs the lines. Each file shows its count and its first five line numbers. The count has no cap, so a file of 400 matches shows 400.
- **The cap is on files, and the files are taken in turn from six groups.** The groups are the source, the tests (fixtures included), the specs, the documents (generated ones included), the change folders and the other files. In path order, the first 60 files of a long list would hide the specs and the tests. The answer lists the groups in a fixed order and says how many files it left out.
- **The search terms of `find_issues` hold no colon and no quote.** The search of GitHub reads `repo:` and `org:` in the query. The model must not name another repository. The client builds the whole query and appends `repo:<repository> is:open`.
- **`read_issue` shows a closed issue's merged pull request from the events.** The last `closed` event holds the commit that closed the issue. `get_commit_pulls` maps the commit to its pull requests. A pull request read as an issue says if it merged from `pull_request.merged_at`.
- **Two prompt files.** `roadmap_stage_tools.md` is the prompt of `base`. `roadmap_stage_tools_extended.md` follows it for `extended`. A prompt that names a tool that does not exist makes the model call it and lose a turn.
- **The setting is a `Literal`.** `StageToolset = Literal["base", "extended"]` sits in `config/defaults.py` with its default. Pydantic refuses any other value and names it. A later issue adds values.
- **The golden set has no GitHub client.** A case plans on the staging commit of a past plan. GitHub holds the state of today, so a read would change the score with time. The tools answer that GitHub is not available.
- **The example ConfigMap sets `toolset: extended`.** It sets the other stage keys. A test does not pin its value.

## Rejected alternatives

- **Add the reads to `RoadmapStore`.** The protocol would grow by four methods, and the in-memory store would need the same four. The store reads through `gh`, and it never reads pull requests as issues (`item` returns None for one). The client does both with fewer lines.
- **Use the search API for `read_issue`.** The search has a quota of 30 requests a minute and returns a body that GitHub may cut. The issue endpoint has the core quota and gives the pull request fields.
- **Show every matching line in `references`.** For `load_settings` that is 786 lines. The answer cap of a tool (8000 characters) would hide most of the files again. The counts and the first line numbers keep each file visible.
- **One prompt file with a marker for the extra tools.** The code would cut the file by text. Two files let a test hold that each prompt names exactly the tools of its set.
- **Make the setting a boolean `github_reads`.** The issue says a later issue adds more values. A name for the set is the form that grows.

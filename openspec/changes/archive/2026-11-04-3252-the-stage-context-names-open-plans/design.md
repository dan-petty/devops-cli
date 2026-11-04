# Design

## Decisions

- **The stage context carries the overlap list, and the gate reads it from the context.**: The gate sees only the context and the reply, so it can refuse a plan that ignores an overlap. The planner spends no tool call on the search.
- **The open pull requests and their changed files come from one GraphQL request for each 100 open pull requests.**: One request returns every field that the context needs and the rate limiter counts it once, so the count grows with the open pull requests and not with the reads of one plan.
- **The reply gets a `dependencies` field (`list[str]`), which the proposal renders as `## Dependencies`.**: The gate reads a field, not prose, and the prompt gives the planner one place for each overlap.
- **The context builder compares paths cited in the issue body, and the proposal gate checks the paths that the reply names.**: The context builder finds overlaps for paths cited in the issue body. The gate ensures that when overlaps exist, the proposal acknowledges them in `dependencies`.
- **A cited metric is a name that `INSTRUMENTS` holds, and its senders are the files that `git grep -w` finds at the staged commit.**: `INSTRUMENTS` is the single list of instruments, and `tests/telemetry/test_telemetry_instruments.py` already ties every metric to it.
- **A pull request whose title has the type `docs(openspec)` is marked as a plan pull request.**: The stage job gives every plan that title, so the mark tells a plan from the pull request that implements it with no extra read.
- **The prompt lists `dependencies` under reply keys, and PR records replay evaluation scores.**: `test_the_top_level_keys_of_the_reply_are_the_fields_of_the_proposal` checks that `StageProposal` fields match the prompt reply keys. Per `docs/ROADMAP_WORKFLOW.md:233`, changes to the prompt or gates state model replay scores before and after.
- **The staged comment states the GraphQL request count.**: The count is the one that `open_pulls` returns: one request for each 100 open pull requests. The comment names it, so a person can judge the extra reads against the rate limit ledger.

## Rejected alternatives

- **Let the planner search the open pull requests with its own `extended` tools.**: `CONTEXT.md` states that the planner works within a budget of tool calls, and the gate cannot check a search that the planner did not run.
- **Read each open pull request with one `gh pr view --json files`.**: `docs/TELEMETRY.md` states that `devops_cli_github_requests_total` counts each paced request, so one read for each open pull request spends the hourly budget of the Service.
- **Reuse the open pull requests that the poll reads.**: `src/devops_cli/roadmap/stage.py` reads no pull request in `read_stage_selection`, and the items of the poll carry no changed files.
- **Parse the `## Dependencies` prose of the proposal to find the overlaps.**: `src/devops_cli/roadmap/stage_change.py` renders the proposal from fields, so a change of wording would hide an overlap from the gate.
- **Take every `devops_cli_` token of the reply as a cited metric.**: `docs/TELEMETRY.md` lists metric names beside other `devops_cli_` identifiers, so a token can name something that is no metric.

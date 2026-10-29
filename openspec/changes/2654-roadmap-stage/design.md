# Design

## Context

Refine sets an item Ready with a design, but nothing turns that design into a branch, an OpenSpec change and a draft pull request. #2653 asks for a job that does this for the Ready P0 and P1 bugs, and for task groups that fit one context window of 128k tokens. This change delivers the command. The Service row (#2659) and the take-over of a staged branch by `worktrees add` (#2657) come after it.

## Decisions

- **Plan first, write after.** `plan_stage` selects the items, calls the model, measures the groups and validates the change in a scratch directory. It writes to no ref and to no GitHub object. `apply_stage` makes the branch, the commit, the push, the pull request, the comment and the record. This is the shape of refine, so `--plan` shows what `--confirm` writes, and a failed validation never leaves a wrong file on a branch.
- **Three model calls at most for one item.** The first call plans the change. A second call replaces the groups when one is over budget. A third call corrects a validation failure. Each of the last two runs at most once for one reply of the model, so the cost of one item has a bound.
- **The measure is the inputs of one step.** For each group the job adds the tokens of the group's task text, of the item (title and body), of every file of the change folder, and of the group's named files packed by `ContextPacker`. A file that does not exist is a file the group creates and costs nothing to read. The packer truncates a file at the budget, so one file over the budget still makes the group over it.
- **The held rule is the rule of `worktrees add`.** `worktree_add.py` holds the check of the worktrees of the clone and of the branches of `origin`. It gets two public functions, and the stage job calls them. An open pull request has a pushed head branch of the form, so the check of branches covers it, and the job makes no request to GitHub for it.
- **The pull request goes through the GitHub session.** The job calls `POST /repos/{repo}/pulls` with `draft` true through `GitHubClient`. The command `devops pr create` runs `gh pr create` in a child process, and the job would start a program of its own to open a pull request.
- **The worktree lives for one item.** `add_worktree` makes the branch on a worktree of the clone, so the HEAD of the clone stays on the default branch. After the push the job removes the worktree and the local branch.
- **The record decides what a run does again.** An item with `stage.needs_split` is left out until a person clears the key or names the item with `--item`. A staged item is held by its pushed branch. So a second run does not call the model again for an item it has done.
- **The slug comes from the title.** The job lower-cases the summary of the title, keeps the ASCII letters and digits, and joins the first six words with hyphens. `is_valid_slug` checks the result. A title with no such word is left out.
- **The pull request body is the permanent what and why.** It holds `Plans #<issue>`, the reason and the list of changes of the proposal, passed through `sanitize_text` so a handle or a link in the model's text pings no one. A text with a closing keyword that is followed by an issue reference stops the item. The person who lands the code rewrites the line to `Closes #<issue>`.
- **Reconcile reads git.** A closed item with `stage.branch` is checked with `git log --format=%ae origin/<default>..origin/<branch>`. The branch is removed only when every author is the identity of the session.

## Rejected alternatives

- **The Copilot coding agent ("assign to Copilot").** #2653 rejects it. #1496 keeps the Copilot allowance for the month, it writes no OpenSpec change, and it cannot use the local models of the gateway.
- **An agent loop that runs the `openspec-propose` skill.** The skill needs a tool loop and many model turns for one change. One structured call has a fixed cost, a schema that is checked, and a reply that tests can fake at the model edge (`model_fake`). The rules of `openspec/config.yaml` go into the prompt instead.
- **A count of characters divided by four.** `count_tokens` in `ai/context_budget.py` returns the exact tokens of tiktoken, which is a dependency, and falls back to that estimate only when tiktoken is missing.
- **A validation after the files are in the worktree.** `--plan` could then not tell a person that the change is valid, and a failure would leave a dirty worktree. The scratch directory holds the same files and costs one copy of `openspec/config.yaml`.
- **`python-slugify` for the slug.** It adds a dependency and a lock change for ten lines of the standard library that keep ASCII words. The cost to build and keep the ten lines is about 1k tokens. The cost to add, lock and audit the dependency is more.
- **A GitHub search for open pull requests that name the issue.** It costs a request for each item. `worktrees add` already relies on the pushed head branch, and the rule stays one rule.
- **A regular expression for the closing keywords.** The job splits the text into words and compares each word with the documented list of GitHub, followed by an issue reference. The repository bans a hand-written pattern where plain string tests do the work.
- **A new comment for a validation failure.** The plan and the exit code already report it, and a comment on each failed round would repeat for every run. Only a stop that waits on a person, a group still over the budget, gets a comment.

## Risks

- A model that cannot split a group under the budget stops the item, and a person decides. That is the intended outcome, not an error of the job.
- A push can succeed and the pull request call can fail. The job then deletes the remote branch, so no remote branch stays without an open pull request.

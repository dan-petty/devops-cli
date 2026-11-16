# Design

## Decisions
- The step owns the order of a round. The caller gives it one `Repair`: the checkout factory, the tier 1 fixer, the model fixer and the scope check. The step opens the checkout only after the bounds, the checks, the caps and the class of the failure, so a closed, a person or a passing pull request costs no clone.
- The command builds the `Repair` only with `--confirm`, after `require_runner`. The model fix runs an agent shell, so it runs only in a runner Job, as the implement job does.
- Without `--confirm` the step returns `planned` before its first write: no comment, no mark, no checkout, no fixer and no push. The mode `plan` of #5027 runs the command without `--confirm`.
- A fixer returns `Fixed(done, reason)`: `done` when it made a commit and its check passes again. The step pushes once, after the fixer that is done. A fixer that says it is done, but leaves the head at the judged head, ends the round as `failed`.
- The checkout takes over the head branch with `add_worktree` and `OriginGit`, as the implement job does: the App must have written every commit past main. The checkout refuses a branch that is not the head branch of the pull request, or a tip that is not the judged head. The push has a lease on the judged head, so it never overwrites a push of another writer.
- Tier 1 runs only for the class `lint`. A test or a type failure is not a format problem. Tier 1 commits the tracked files that its fixers changed, then runs the check of each fixer again (ADR 0021 section 8: "then the check again"). When the checks pass, the round pushes with 0 model requests. When a check still fails, the commit stays, and the scope check and the model fix run on top of it in the same round.
- The model fix uses the task `ai.tasks.fix_checks` with no ladder, so a model trial moves this job alone (#5903). The task has the window of the implement task (128,000 tokens) and takes the model of `ai` until a source sets one.
- `StepBudget` takes a `TokenCap`: a fixed cap of the new tokens of the step, which replaces `step_token_budget` and its extension, and which the stop names. The cap of a fix-checks run is `roadmap.fix_checks.token_budget`, 16,000,000 new tokens by default, by the owner direction of 2026-11-16. ADR 0021 section 8 named 4,000,000 tokens for each unit; this change amends it.
- The step does not wait for the checks after its push. The watch row marks a bot draft ready when its verdict is ready (#5024). The step also marks a draft ready when a later call finds a draft that it repaired, with every check passing, and `draft_readiness` answers ready. Only an implement draft gets this mark: a plan draft keeps the holds of `stage_ready`.

## Rejected alternatives
- The command builds the worktree before it calls the step, and passes it as `source`. Rejected: a closed or a person pull request would cost a clone, and the take-over refuses a person branch with an error before the step can return `stopped`.
- The step waits for the checks after its push, as the implement job does. Rejected: the Job would hold a runner pod and a model Job slot for the length of the checks, and the watch row already marks a ready draft.
- A pydantic-ai `UsageLimits` token limit for the cap. Rejected: it counts the input tokens that the provider reads from its cache, and the owner's cap counts new tokens.

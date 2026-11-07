# Design

## Context

See proposal.md for the scope (#4085, group 2 of #3769). Other command groups are separate changes.

## Decisions

### 1. `gh` is answered at the process edge, with a fresh quota in the ledger
- **Decision**: `gh_edge` records a fresh quota for `core`, `graphql` and `search`, and returns `process_fake`. A test then scripts `gh` by argument prefix (`answer_gh`), in order (`script_gh`), or by a word in an argument (`mentions`).
- **Why not answer `gh api rate_limit` through the fake**: a later, wider answer such as `["gh", "api"]` would shadow the quota answer, and the quota read would parse the wrong text.
- **Rejected**: patch `run_gh` of the command module. It is a name inside `devops_cli`, and it skips the pacing and the masking that the real `run_gh` does.

### 2. The roadmap runs for real on the in-memory store
- **Decision**: the status, the labels and the form check of `pr create` and `pr ready` run on `roadmap_store`. The closing issues come from a `gh api graphql` answer.
- **Rejected**: keep the three autouse patches (`set_delivered_status`, `_labels_recorded`, `_form_checked`). They hid the form of the title and the body, and the tests used texts that break it.

### 3. A private helper is tested through its command
- **Decision**: `_fallback_create_pr`, `_render_pr_list_fallback`, `_execute_update_branch`, `_process_candidate_pr_row` and `_get_repo_labels` are reached through `pr create`, `pr list`, `pr update` and `gh labels list`.
- **Rejected**: move the helpers to a domain package. The commands hold no logic that a second caller needs.

### 4. The mutation budget is reached, not patched
- **Decision**: the budget tests build a board with 27 changes against the default budget of 25.
- **Rejected**: keep a patched `MutationBudget`. A test then checks a limit that the product does not use.

### 5. The cache options of `gh api` are read from the clock
- **Decision**: a cached read starts `gh` once while the time to live lasts, and again after it. The test moves the clock fake by 20 s and then by 10 s against a time to live of 25 s.
- **Rejected**: read the `use_cache` and `cache_ttl` keyword arguments of a mocked `run_gh`. They are internal names.

### 6. Pacing of a write is read from the waits
- **Decision**: the REST fallback of `pr create` posts with an implicit POST. The test notes which command follows each long wait of the clock fake: the `gh pr create` write and the POST wait, and the lookup read between them does not.
- **Rejected**: patch `GitHubRateLimiter.acquire`. It is an internal method.

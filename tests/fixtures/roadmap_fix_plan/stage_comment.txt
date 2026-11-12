<!-- devops roadmap stage -->
Staged: branch `fix/2530-fix-check-readiness-base-and-monitor`, draft pull request #4980. The pull request plans the item and closes no issue.

The task groups, with the tokens of the inputs of each step, for a budget of 64000 tokens:

1. Read the compare answer's files in the GitHub client: 26840 tokens
2. Readiness reads the compare and reports the file limit: 48611 tokens
3. Return a closed pull request's status before any check read: 25026 tokens
4. Print a terminal monitor result with no check count: 36849 tokens
5. Plan the compare request in the check-readiness dry run: 23398 tokens

A model review of the plan found these open findings. The stage keeps this pull request a draft with the label `plan/needs-fix` until a later round clears them:

- `criterion_dropped` at specs (Readiness reads the file list at the merge base): The issue's criterion that no request path of the readiness run ends with the pulls files path has no task that delivers it: `devops pr check-readiness` also calls `read_draft`, which requests `pulls/{number}/files` for an implement pull request, and no group of the plan changes `src/devops_cli/roadmap/implement/implement_pull.py`. Evidence: "No request path of the readiness run ends with `pulls/{number}/files`, and the verdict holds no not-grounded blocker naming those folders."

A model review of the plan found these points. They stop no draft, and a person judges them:

- `other` at group 2: The head-naming rule has only a fork case and a base-repository case, but GitHub reports the head repository as null for a pull request whose fork was deleted, so the plan builds a compare head with no owner instead of falling back to the head commit sha. Evidence: "repository: str | None = Field(default=None, validation_alias=AliasPath("repo", "full_name"))"

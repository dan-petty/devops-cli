# Design

## Decisions

- The Status write runs after the claim, and only when the claim is made. An item that another owner holds is not the agent's work, so its Status stays.
- `set_claimed_status` sits in `pull_status.py` beside `set_delivered_status` and reads the same table `_REPLACES`, so one table holds the forward rule of every Status write of an agentic coder.
- The claim keeps every Blocked item Blocked. `devops pr create` moves a Blocked item with `implement.stopped` because its pull request is the fix of the stop. A claim is only the start of the work, and the clear rules of a stop (`stop_clear.py`) stay the one way out of Blocked before a pull request.
- The report gets its own field `status_error`. The owner label is set when only the Status write fails, so `claimed` stays true and `claim_error` stays empty. The warning names the reason, and the next `devops pr create` sets In Progress by the same rule.
- `progress_as_agent` imports `pull_status` inside the function, so the help of `devops repos` loads no more modules.

## Rejected alternatives

- Set the Status in `apply_claim`, so that `devops roadmap claim` sets it too. A person can claim an item only to hold it, and the issue asks only for the claim of `devops repos worktrees add`.
- Write the owner and the Status in one request. The store writes one field family in each `set_field`, and a second write keeps the store contract unchanged.
- Report a failed Status write in `claim_error`. The report would then say that the claim failed while the item holds `owner/agent`.
- Use the rule of `set_delivered_status` with its exception for a stop of the implement job. The acceptance of #4685 asks that a Blocked item stays Blocked.

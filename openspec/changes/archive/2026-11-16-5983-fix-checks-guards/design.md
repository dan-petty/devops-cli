# Design

## Decisions
- The live Job guard uses `job_holds` (`implement.job` set and `implement.job_state` empty), not the bare `implement.job` that `fix-plan` reads. The record keeps the name of a Job after it ends, and each implement draft has one, so the bare key would stop the step on every implement draft. The result is `skipped`, as for a moved head: the item comes back when the Job ends. The guard comes before the owner label, so the reason names the Job.
- The step skips a repeated round; it does not count it against the cap. A count still runs the model on the same failure up to the soft cap (3 rounds, up to 48,000,000 tokens) and posts the infrastructure comment each time. A skip costs no model request and no write, and the key `<head>:<check>` is the idempotency key of the unit in ADR 0021 section 8. The guard reads only the first failed check, which the step takes; a skip of a later check would make the step alternate between two keys.
- The cap of heads moves after the ready path, not to a count of the heads that the step pushed. The step records the judged heads, not the pushed heads, and the implement Job and `fix-conflict` also push. The move keeps the record and stops only a repair.
- Tier 1 takes its causes from `tier1_causes`: the class lint, a docs failure (the text of `devops docs check`), or a lockfile failure (the text of uv). The function is pure and lives in `fix_checks.py`, so the infrastructure decision and the fixers read the same causes. A lint failure keeps `devops docs generate`, as before.
- The lockfile trigger is the uv text "`uv.lock` needs to be updated", not the file name. The log of `setup-uv` names `uv.lock` in each job, and the wide trigger would start tier 1 and stop the infrastructure wait on every setup failure.

## Rejected alternatives
- Count failed, stopped and wait rounds against the soft cap. Rejected: see the second decision.
- Store the identifier of the check run in the key, so a rerun after a wait gets a round. Rejected for this change: the key format `<head>:<check>` is shared with the implement Job and ADR 0021. A rerun that fails on the same head stays skipped until a new head; the comment of the wait tells a person.
- Let `fix-checks` ignore `owner/service`, as `fix-conflict` does. Rejected for this change: #5027 decides how the launcher claims the item.

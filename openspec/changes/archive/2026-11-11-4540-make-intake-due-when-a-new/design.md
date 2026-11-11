# Design

## Decisions

- **The issue listing, not the issue events.** The events report no opened issue (proposal, Feasibility). The rule compares the newest issue number with the number that the intake record keeps, so it does not depend on the clock of the pod.
- **The record keeps the newest issue as the round starts.** `_run_intake_adapter` reads the newest issue before `plan_intake` lists the candidates. An issue that opens during the round is newer than the record, so the next poll runs intake again. That round decides nothing that was decided.
- **A scoped update does not move `newest`.** If it did, the scoped update of issue 11 would hide issue 10 when the delivery of issue 10 was lost. So the poll after a scoped update runs intake once. That run finds the new issue decided and sends no model request for it.
- **A lazy read.** The rule reads the newest issue only when no reopened issue and no fresh candidate makes intake due, and only when the record has a newest issue. `run_due_jobs` caches the read for the round, and a round with no trigger makes no read, as before.
- **Pull requests do not count.** The listing holds pull requests too. The store reads one page of 10 entries and takes the first entry that is no pull request. A page of only pull requests gives None, and the store asks for no later page, so a repository with only pull requests never reaches the page cap of the session.
- **No newest issue on the record means no read.** A record from before this change, or one that no intake round wrote, keeps the old rule until the next intake round. The row's interval brings that round within 29 minutes.

## Rejected alternatives

- **`ChangeKind.OPENED` from the issue events.** GitHub does not report it in that feed.
- **The creation time of the newest issue against the last success of intake.** It needs no new record field, but a pod clock that runs ahead of GitHub can hide an issue that opened during the round.
- **`per_page=1`, following pages until an issue.** A run of new pull requests costs one request each, and a repository with only pull requests reads up to the page cap and raises.
- **Count every new pull request too.** Agents open many pull requests a day, and each one would cost an intake round that reads every issue.

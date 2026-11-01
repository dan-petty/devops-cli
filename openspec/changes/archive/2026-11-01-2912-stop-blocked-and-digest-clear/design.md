# Design

## Decisions

- **One Status function derives Blocked.** `derive_status` gets the fact `stopped` (the record holds `implement.stopped`). The order is: In Progress while a Job holds the item, else Blocked while a stop is on record, else Planned when the plan is on the default branch, else Ready. The runner stop and the Job-report stop call it, so no code names the Status by hand. The sweep still writes only an item that holds Ready or Planned with the label that a job recorded. So an old stop (Ready with `implement.stopped`) becomes Blocked in the next round, and a person's label stays.
- **The digest is recorded at the create of the Job**, in `implement.job_digest`, in the same write that records `implement.job` and the claim. This is the stop record: a stop always follows a Job, and the next Job overwrites the key. The Feasibility section gives the evidence for this source.
- **The clear rules run in the Service round, not in the runner.** The runner holds no Kubernetes token and sees no CronJob. The round reads the template once, and only when an item needs the digest. The module `stop_clear.py` holds the two rules and the comment texts.
- **Retry comes before digest.** A person's `implement: retry` clears at once. Else a different digest clears one time. The comment names the rule, and for the digest rule both digests.
- **One clear for each digest, with no new counter.** A clear removes `implement.stopped`. The next Job overwrites `implement.job_digest` with the digest of the template. A second stop on that digest then finds both digests equal, and no rule fires. A third digest clears again once. Digests change only when a release rolls, so there is no loop. A test runs many rounds on one digest and counts the Jobs.
- **A Blocked item with a running Job, or a claim, is not cleared.** A Job that the round did not report yet still holds the item. An item that an agent or a person claimed is not the Service's.
- **The ledger of failed rounds is unchanged.** It suspends a row after three failed rounds on the same input. It counts rounds, not stops.
- **The stop comment of the runner does not carry the digest.** The runner has no Kubernetes token. The report comment of the Service names the digest, and the Service reads it from the record.
- **The digest is the text after `@`.** `k8s/image_pins.py` reads an image reference the same way. A reference grammar library is not needed to split on one separator.

## Rejected alternatives

- **Read the digest from the pod `imageID` or the Job spec at report time.** A Job is deleted after one day, a `gone` Job has no object, and a pod that cannot pull has no `imageID`. The record has none of these limits.
- **Record the digest in the stop comment only.** The Service would parse its own comment to compare digests. A record key is read without parsing, and ADR 0016 keeps job facts in the record.
- **A counter key `implement.cleared` for the bound.** The digest already bounds the clears. A second key could drift from it.
- **Let the runner write `Blocked` and the Service never derive it.** Two writers would name one Status. The issue asks for the one function of the Status.
- **Auto-retry with a delay on the same digest.** It repeats a known failure and spends runner time. The issue says a second stop on the same digest waits for a person.
- **Clear in the judge of `plan_implement`.** The plan must make no write. A clear is a write.

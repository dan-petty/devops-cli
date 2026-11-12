# Design

## Decisions

- **The version is a time.**: A record from before this change holds no version. The time of refine's last comment, which `_wait_state` already gives, dates such a record against the same constant. One constant then serves the recorded versions and the old records.
- **The recorded version counts first.**: A round that asks a person again writes its comment at the time of the round, which can be before a later version takes effect. The recorded version of that round stays exact. A value that is no time counts as no version, with a warning.
- **Only a wait on a person ends.**: A `blocked` wait ends when its blockers close. An `edit` or `failed` wait ends with a body edit, and a `retry` is no wait. A rule change does not change these exits.
- **Only a written proposal records the version.**: `_refine_marks` writes the step of every proposal, the `person` step included. The record-only path (an item too big, or a job failure) writes `edit`, `retry` or `failed`, which the version does not end, so it records none.
- **The version is the release of 0.72.0.**: The merge of #3632 is 15 minutes earlier, and no person wait has a comment time between the two. A later change sets the day of the change. The rounds of the released image record the value of the constant, so the comparison stays exact.
- **The round limit bounds the cost.**: The old waits go through the normal selection and its limit (`DEFAULT_ROADMAP_REFINE_LIMIT`), so a round makes no more model calls than before.

## Rejected alternatives

- **An integer version.**: A record with no version then needs a second constant, the time of version 1, to tell the 50 old waits from the 46 new ones. One time value does both.
- **Treat a record with no version as old.**: That gives the 46 waits that the current rules set a new round too. 36 of them hold a "(a person decides)" question, and a new round would ask the person again in a second comment.
- **A one-time script that writes the version to the records.**: It needs a live run in the right order with the release, and it does not serve the next rule change.
- **Run `devops roadmap refine --item <number>` for each old wait.**: It is a manual step for each rule change, and it does not serve the next one.

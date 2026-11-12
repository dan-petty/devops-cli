# Design

## Decisions

- **The store guards the equal path.** `set_marks` reads the issue before its write already. The guard compares the Status of that read with the Status that the store read, in the same lock as the write. So the window between the check and the write is the window of `set_field`, and the guard adds no request.
- **The guard is a keyword, not a default.** Before #5109, `set_marks` had no guard, and refine, stage and the runner Job call it for marks that do not depend on the Status. Only `write_status` gives `unchanged`, because only its caller decided on the Status.
- **The store's own write counts as read.** The guard takes the read value from the last write of the store when there is one, as `set_field` does. So a caller that holds the Item from before a Status write of the same store is not refused.
- **No Status goes into the record on the equal path.** The design of #5018 keeps a record that differs from an equal label as it is, because `repair.py` reads a recorded New as "a job set New". The guard keeps that: it reads and compares, and writes only the marks and the body.
- **A refused write is not written again.** The caller decided on the old Status. The next round reads the issue again and decides again (ADR 0002).

## Rejected alternatives

- **Write the label with `set_field` on the equal path too.** `set_field` has the guard, but it records the Status in the job record. Rejected: it reverses the decision of #5018 on a record that differs from an equal label.
- **Read the issue in `write_status` before `set_marks`.** Rejected: it costs one more read for each write of marks, and the check and the write are then two reads apart.
- **Guard every `set_marks` call on the Status.** Rejected: it refuses marks that do not depend on the Status, such as the record of a model failure, and it changes callers that the bug does not touch.

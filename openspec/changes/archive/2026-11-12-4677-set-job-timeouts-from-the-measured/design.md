# Design

## Decisions

- A job limit is about two times the longest run of the job, rounded up to whole minutes, and 5 minutes at least. A job that did little work in the window, such as Rule Pack Tests, gets 5 minutes.
- DevContainer Image gets 20 minutes, about three times its longest run of 416 s, because its job builds the image with no cache when the base image changes.
- A step limit applies to the step that runs the gate or the tests. The step limit leaves time for the steps before it and after it, from the sum of their longest runs:
  - Static Analysis: 71 s before the gate, 180 s for the gate, and 42 s for the Security Scan, the SARIF upload and the post steps. The total is 293 s of the 360 s limit.
  - Test shard: 66 s before the gate, 1,020 s for the gate, and 6 s after it. The total is 1,092 s of the 1,200 s limit.
  - Service Image Tests: 244 s before the suite, 840 s for the suite, and 40 s after it. The total is 1,124 s of the 1,200 s limit.
- The test steps have limits above the 600 s hang bound of one test, so pytest-timeout fails a hung test first and the run goes on.
- The contract test compares only the listed jobs. A job that another pull request adds to `ci.yml` does not fail it, and the general test holds the step limits of the new job under its job limit.

## Rejected alternatives

- Set CodeQL to two times its longest run. Rejected: #4651 gave it 15 minutes for a longest run of 212 s, and 15 minutes is under the 20-minute bound of this item.
- Keep Changed-Test Independence at 30 minutes. Rejected: #4509 merged, and the runs after it took 174 s at most.
- Wrap the test commands in `timeout` of coreutils in this change. Rejected: the item that gives the test row its own bound does that, and the step limit is the outer bound of that row.

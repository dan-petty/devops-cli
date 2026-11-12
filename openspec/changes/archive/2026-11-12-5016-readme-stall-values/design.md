# Design

## Decisions

- **Read the whole README.** The test reads all of `k8s/README.md`, not only the Deadline bullet. Item 16 also states the stall (in minutes), so one pass finds a drift in both places.
- **One value for each pattern.** The test collects every value that a pattern finds and compares the set with the one default. An empty set fails, so a change of the sentence makes the author change the test. A second statement with another value also fails.
- **State the margin and the minutes from the defaults.** The expected margin is the stall minus the watch, and the expected minutes are the stall divided by 60. So a later change of a default, such as the change of item `implement-ends-at-draft`, changes the expected text without a new constant in the test.

## Rejected alternatives

- **Generate the bullet from the defaults.** `devops docs generate` writes the reference documents, not `k8s/README.md`, which is hand-written prose. A generator for one bullet costs more than one test case.
- **Check only the stall and the watch.** The issue names these two. The extension and the ceiling are in the same bullet and can drift in the same way, as the extension did before #3223. Two more cases cost nothing.

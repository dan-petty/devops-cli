# Design

## Decisions

The decisions are in ADR 0021 (`docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md`). In short:

- **The Service keeps only the webhook router.** At the end of tracker #4517 it runs no row, holds no volume and runs 2 replicas with `RollingUpdate`.
- **One pod for each unit of work.** Only the router and the sweep create units. A unit that makes more work due sets a due mark.
- **The engine is Argo Workflows**, after the go verdict on #1535. Stage moves first to a plain Job on the path of #2667. The controller manages namespace `devops` with `templateReferencing: Strict`.
- **`valkey-roadmap` holds the coordination state**, under nine rules. GitHub stays the source of truth, and a read-back repair, not a lock, guards a job record.
- **One request budget** in `limits` moving windows for all pods of the App installation.
- **A cold pod gets warm** from its image layers, a blobless clone and Valkey.
- **The amended records keep their text.** Each gets a note at its top, as ADR 0001 and ADR 0003 have. The note of ADR 0017 corrects its lane and poll lines.
- **The naming rules** belong to the naming record of #4533. ADR 0021 cites #4533 and tracker #4517 until that record merges.

## Rejected alternatives

- **Edit the stale lines of ADR 0017 in place.** A record keeps the text that was approved. The note at its top and ADR 0021 give the correction.
- **A spec delta for the new design.** The steps of tracker #4517 are not built. A requirement now would describe behavior that the code does not have. Each step adds its own delta.
- **Keep the no-go column of the design study.** The verdict is go, so the record keeps only the engine path and lists the plain Jobs path as an option not taken.
- **Each rejected option of the engine and the state** is in the Considered Options section of ADR 0021, with its evidence.

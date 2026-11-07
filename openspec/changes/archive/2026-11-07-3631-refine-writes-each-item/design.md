# Design

## Decisions

- **`plan_refine` calls an optional `RefineWriter` for each item.**: The loop already holds the result of each item the moment it is done. A callback adds no thread and no second pass, and a plan run with no writer stays read-only.
- **`apply_refine` and `RefineWriter` share `_apply_result`.**: One write path serves the CLI and the Service, so a write rule changes in one place.
- **The next round skips a written item through its Status and marks.**: `select_candidates` already reads them. A round cursor in a file would add state that a crash or a second lane can make stale.
- **A failed write is logged, counted and the round goes on.**: One bad item must not lose the work of the others. The round still fails at its end, with the items named, so the failure ledger counts it.
- **Rejected credentials and the stop of the Service end the round.**: Both would fail every later write, and the stop must end the round at once (#2753).
- **The round logs through the existing logger, with texts in `RoadmapMessages`.**: The project keeps output strings in the catalog.

## Rejected alternatives

- **Keep the batch write after all items.**: A stop loses every finished item. This is the defect.
- **Write from a background thread while planning goes on.**: It adds concurrency with no gain, and a stop still loses the item in progress.
- **Keep a round cursor in a file.**: It adds state that can go stale, against ADR 0001.
- **Abort the round at the first failed write.**: One failed item would lose the work of the other items.

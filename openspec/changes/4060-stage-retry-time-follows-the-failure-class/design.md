# Design

## Decisions

- **One table, `RETRY_AFTER`, beside `ACTION_BY_CLASS` in `failure.py`.**: The class decides the action and the wait, so both tables sit in one module and use one type, `MappingProxyType`. A test holds that its keys are exactly the classes of `CLASS_BY_EXCEPTION`, so a new stage class cannot miss a wait.
- **The selection computes `failed_at + RETRY_AFTER[class]` and stores nothing.**: The record then holds facts (time and class), and a change of the table applies to records that exist. A stored retry time would go stale when the table changes.
- **A missing class and an unknown class both wait as `ci_infra`.**: A record from before #4056 has no class. A class string that is no `FailureClass` (a value of a later or an older image) must not stop the selection with an exception. The wait of `ci_infra` is the short, safe one: the item comes back in 1 hour and the job decides again.
- **`head_moved` waits 0.**: The item changed while the job worked, so the next round reads it again. `until` equals `failed_at`, so `until <= now` is true and the item is taken in the same round that sees it.
- **The setting goes and nothing replaces it.**: The project is alpha and keeps no shim. The wait is a property of the class, and the table holds it. A person who wants another wait changes the table by a pull request.
- **The live ConfigMap needs no change.**: It holds no `retry_hours`, and `RoadmapStageConfig` ignores an unknown key, so the order of the rollout does not matter. A test holds the second fact.

## Rejected alternatives

- **Keep `retry_hours` as a cap or a default for an unknown class.**: It keeps a second source of the wait and a setting that no class reads. The unknown case has a rule (`ci_infra`), so the setting has no job. Rejected: it is a shim.
- **A `RETRY_AFTER` key for each of the 19 classes.**: The stage records only five classes (`CLASS_BY_EXCEPTION`). The other 14 are classes of the implement job, whose retry follows `ACTION_BY_CLASS` and `implement.continuations`. Rejected: a key that no stage failure reaches is dead data, and the test of the keys would fail on it.
- **Store the retry time in the job record (`stage.retry_at`).**: It adds a write and a key, and the time goes stale when the table changes. Rejected: the sum of two stored facts is cheap to compute.
- **A `None` value for a class that never waits.**: The caller would branch on `None`. `timedelta(0)` gives the same result with no branch.

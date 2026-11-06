# Design

## Decisions

- **The evaluation gets its own read-only roadmap.** `SeededRoadmap` answers the five reads of `IntakeReads` and has no write method, so a run cannot change a roadmap. `closures` and `comments_on` return `[]`, and `evidence_holds` returns `False`, so no case can set P0. `plan_intake` takes `IntakeReads`; `RoadmapStore` already satisfies it, so no caller changes.
- **The fault is a mode of the fake.** `fail_write(*, at, applied, write, item)` keeps the semantics of the old `Fault`: the `at`-th matching write raises `GitHubOperationError("HTTP 502")` once, and with `applied` the write applies first. A decorator on each write method counts the write and applies the fault. `close` calls the private comment body, so it does not count as a comment write. `fail_listing` and `listed` replace `ListingStore`.
- **The contract suite covers the fault on both adapters.** `GitHubFake.fail_write` fails the Nth request that writes with a 502, before or after it applies. The two new cases use `label_issue`, one request on the GitHub adapter and one write on the fake. The listing fault is a feature of the fake only, and is tested where it is used.
- **The open plans follow the move.** `3187` no longer moves `memory_store.py`, and `3254` declares its registry counts in the fake.

## Existing code to reuse or keep passing

- `tests/roadmap/test_roadmap_store_contract.py` and `tests/roadmap/test_roadmap_duplicate_eval.py` keep their assertions.
- The `roadmap_store` fixture of `tests/support/roadmap.py` keeps its name.

## Rejected alternatives

- **Keep the fake in `src` as a production type.** `docs/TESTING.md` allows an in-memory implementation in `src` only if production uses it. Production used two reads of it, and the class shipped 779 lines of seeding helpers for them.
- **Move the evaluation under `tests/` or `scripts/`.** `devops roadmap eval intake` is a shipped command, and its case file ships in the package.
- **Build the evaluation roadmap from `GitHubRoadmapStore` over a recorded session.** It needs a recorded page set for 16 cases to read one issue and one file, and it would test the GitHub store, not intake.

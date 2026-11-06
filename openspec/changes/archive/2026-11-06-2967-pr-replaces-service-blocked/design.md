# Design

## Decisions

- **Put `Item.holds_service_stop` in `src/devops_cli/roadmap/store.py`, beside `Item.field_value`.**: The rule reads only the Status and the job record of the Item. `pull_status.py` runs at the start of `devops pr`, and the startup-import budget forbids an import of `status_sync.py`, which pulls in `pydantic_ai` through `roadmap/stage.py`. The module `store.py` is imported already.
- **Make `is_service_stop` call `Item.holds_service_stop`.**: The issue asks for the same rule without the claim and Job checks. One method holds the shared part, so a change of the rule changes both places.
- **Add the test in `set_delivered_status` beside the `_REPLACES` test.**: `_REPLACES` stays a static table of Statuses. The Service-stop case depends on the record of the item, so it is a second condition in the one loop.
- **Skip the claim and Job checks for a pull request.**: The pull request is the fix. A person who fixes the item holds a claim, and the Job that stopped is over.
- **Leave `implement.stopped` on record.**: The Service starts no Job for a stopped item until a trusted `implement: retry` comment, so it starts no Job over the pull request. If the pull request closes with no merge, the item stays stopped and a person decides.

## Rejected alternatives

- **Put the function in `src/devops_cli/roadmap/status_sync.py`, next to `job_holds`.**: The row `startup-imports` of `devops ci` failed: `devops pr --help` then imported `pydantic_ai`.
- **Add Blocked to `_REPLACES`.**: It replaces a `status/blocked` label that a person set by hand. ADR 0002 says a job never reverts a change of a person, and the spec says a Blocked item stays Blocked.
- **Read the events of the issue to find who set the label.**: It adds a request for each item. The job record is on the item already and holds the same fact.
- **Clear `implement.stopped` with the Status.**: The item would then be Ready-like for the row `implement` while a pull request is open, and the Service could start a Job over it.

## MODIFIED Requirements

### Requirement: Renovate updates on a fixed schedule within the CI cap
The preset SHALL use the time zone UTC and the schedule Monday, give a patch update the schedule `at any time` in its own branch, group the non-major updates of each ecosystem, open at most 2 pull requests an hour and keep at most 8 open, not push an open branch again only because `main` moved (`rebaseWhen: conflicted`), push an open branch only in the schedule of that branch (`updateNotScheduled: false`), and run lock file maintenance on Monday.

#### Scenario: The schedule and the limits are read
- **WHEN** a test reads `.github/renovate/base.json`
- **THEN** `schedule` is `["* * * * 1"]`, the only patch rule sets `["at any time"]`, `prHourlyLimit` is 2, `prConcurrentLimit` is 8, `rebaseWhen` is `conflicted` and `updateNotScheduled` is false
- **AND** each ecosystem group matches only minor and patch updates

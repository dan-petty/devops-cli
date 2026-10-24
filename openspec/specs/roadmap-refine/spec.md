# roadmap-refine Specification

## Purpose
The items that a round of `devops roadmap refine` looks at without `--item`, the order in which the round takes them, the one cap on their number, and the keys of the roadmap configuration that the roadmap jobs read.

## Requirements

### Requirement: Only the limit stops a refine round
Without `--item`, `devops roadmap refine` SHALL take up to `--limit` items in this order: each open milestone's New items, nearest milestone first, then the backlog's P0 and P1 New items, then the backlog's other New items, each place by priority. The number of Ready items in the open milestones and in the backlog SHALL NOT stop a round.

#### Scenario: A backlog full of Ready items
- **WHEN** the backlog holds twelve Ready items and New P3, P2, P1 and P3 items, an open milestone holds one New P3 item, and refine runs with `--limit 4`
- **THEN** refine asks the model about the milestone's item, the backlog's P1 item, the backlog's P2 item and the backlog's first P3 item, in that order, and about no other item

### Requirement: The roadmap configuration holds only the board
`.github/roadmap.toml` SHALL hold the key `board` and no other key. A file that sets another key SHALL fail with a configuration error that names that key.

#### Scenario: A file that sets a Ready target
- **WHEN** the roadmap configuration sets `board = 2` and `refine_ready_target = 12`
- **THEN** the read fails with a configuration error whose key is `refine_ready_target`

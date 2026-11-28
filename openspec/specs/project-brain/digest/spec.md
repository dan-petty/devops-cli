# project-brain/digest Specification

## Purpose

The brain digest that the alternatives check reads before its one model call (ADR 0023 section 1): the near items of the entry of an item in the brain index, with their dates, verdicts, tools and ADR status, its bound of 2,000 tokens, the key `brain` of the request, the record `alternatives.brain_used` and the setting `roadmap.brain.digest`.

## Requirements

### Requirement: The digest holds the near items of the index entry
The alternatives check SHALL build the digest of an item from the `near` field of the entry of the item in the brain index, in the order of that field, and SHALL hold at most 5 near items, each with its verdict and the canonical id of its tool. A near item with no entry in the index, or with an entry of another schema or of a wrong form, SHALL give no digest entry.

#### Scenario: Five near items
- **WHEN** the fixture brain holds an entry for the item whose `near` field lists 5 items, each with a verdict and a canonical tool id
- **THEN** the digest holds the 5 items in that order, with their verdicts and canonical tool ids

#### Scenario: A near item with no entry
- **WHEN** the entry of the item names 4 near items, the index holds no entry of the second, and the entry of the third is of another schema
- **THEN** the digest holds the first and the fourth near item only

### Requirement: The digest stays at or below 2,000 tokens
The JSON text of the digest SHALL hold at most 2,000 tokens by the token count of the ADR cut, and the digest SHALL cut whole entries to do so.

#### Scenario: More entries than the cap
- **WHEN** the fixture brain holds 5 near items whose entries hold about 4,000 tokens together
- **THEN** the digest holds whole entries only, and its token count is at most 2,000

### Requirement: Each digest fact has its date
The digest SHALL hold the date of the check of each near item, which is the date of its verdict and of its tool.

#### Scenario: A dated verdict
- **WHEN** the fixture brain holds a near item with the verdict `partly` and the check time 2026-11-01 09:30 UTC
- **THEN** the digest holds that verdict with the date 2026-11-01

### Requirement: The digest holds the ADR status of a tool
The digest SHALL hold, for the tool of each near item, the number of each ADR in force that the check reads and that rejects the tool under a rejected option.

#### Scenario: A tool that an ADR rejects
- **WHEN** the fixture brain names Temporal and Argo Workflows, and a fixture ADR 0008 in force rejects Temporal under a rejected option and chooses Argo Workflows
- **THEN** the digest holds Temporal with ADR 0008, and Argo Workflows with no ADR

### Requirement: The digest holds no area verdict and no ring while the index holds none
The digest SHALL hold no area verdict and no ring of a tool while the brain index holds no area check and no ring.

#### Scenario: An index with no area check
- **WHEN** the fixture brain holds 2 near items of the item and no area check
- **THEN** the digest holds the 2 near items and nothing else

### Requirement: The request holds the digest
`alternatives_request` SHALL hold the digest under the key `brain` as a list of its entries, and SHALL hold no `brain` key when the digest is empty.

#### Scenario: A digest and an empty digest
- **WHEN** the digest of one item holds 2 near items, and a later item of the same run has no entry in the index
- **THEN** the first request holds the key `brain` with 2 entries, and the second request holds no `brain` key

### Requirement: The digest adds no model call
The check SHALL add the digest to its existing model request and SHALL make no other model call.

#### Scenario: One model call
- **WHEN** one item is checked with a digest of 5 near items, and the same item is checked with an empty digest
- **THEN** each run makes the same number of model calls

### Requirement: No brain gives an empty digest
The check SHALL use an empty digest and SHALL run as before when the brain is unavailable: the process names no `roadmap.state.url`, the store does not answer a read, or the index holds no entry or no near item of the item.

#### Scenario: Valkey down
- **WHEN** the Valkey read fails, the index is not built, or the run names no `roadmap.state.url`
- **THEN** the request holds no `brain` key, and the check writes the verdict of its reply and no `alternatives.brain_used`

### Requirement: The digest switch turns the digest off
The setting `roadmap.brain.digest` SHALL take `off` or `on`, SHALL default to `on`, and SHALL make no read of the brain index when it is `off`.

#### Scenario: The default and the off value
- **WHEN** `roadmap.brain.digest` is unset in one run and set to `off` in the next run
- **THEN** the first run reads the brain, and the second run sends no command to the store and its request holds no `brain` key

### Requirement: The check records the brain entries that it used
A written check SHALL record `alternatives.brain_used` with the ids of at most 10 brain entries that its digest used, `item:<n>` for an item and `tool:<id>` for a tool, the entry of the item first, in the one write of its block and its other marks. A check whose digest used no entry SHALL clear the key.

#### Scenario: Eleven entries
- **WHEN** the digest takes 11 brain entries: the entry of the item, and 5 near items that each name a tool of their own
- **THEN** `alternatives.brain_used` holds the first 10 entry ids, and the check makes one write of the issue and one comment

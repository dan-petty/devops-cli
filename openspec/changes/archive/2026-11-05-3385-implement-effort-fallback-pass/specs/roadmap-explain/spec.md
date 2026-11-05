## ADDED Requirements

### Requirement: The implement verdict names the effort set and the fallback pass
`devops roadmap explain` SHALL name, on a line under the implement job, the effort set of the job and whether the fallback pass applies to the item. The fallback pass SHALL apply to an item only when the item's effort is the effort of the pass in use and that pass is not the first value of the set. When the filter names `effort`, the line SHALL say that the set does not apply.

#### Scenario: A medium-effort item uses the fallback
- **WHEN** the user runs `devops roadmap explain <number>` on a Ready medium-effort item while no low-effort item is selectable
- **THEN** the output names the effort set `low,medium` and says that the fallback pass applies to the item

#### Scenario: A medium-effort item waits for a low-effort item
- **WHEN** the user runs `devops roadmap explain <number>` on a Ready medium-effort item while a Ready low-effort item is selectable
- **THEN** the implement job is `no`, the reason names the effort `low` that the run takes first, and the output says that the fallback pass does not apply to the item

#### Scenario: A high-effort item is outside the set
- **WHEN** the user runs `devops roadmap explain <number>` on a Ready high-effort item
- **THEN** the implement job is `no` and the reason names the family `effort`, the values `low or medium`, and the value `high`

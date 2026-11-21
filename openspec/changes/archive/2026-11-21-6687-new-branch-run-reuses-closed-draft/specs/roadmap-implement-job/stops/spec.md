## MODIFIED Requirements

### Requirement: A return withdraws the pushes of earlier Jobs first
`prepare` SHALL write `implement.base` once: the tip of the branch on `origin`, or `new`. Before a return to New, `publish` SHALL withdraw what earlier Jobs pushed, with a lease on the tip that `prepare` found: it SHALL push a sha base back when the tip differs, and for `new` SHALL delete the branch that `prepare` found and close the recorded draft. A withdraw that ran SHALL clear `implement.base` at once. A withdraw that fails SHALL stop the item as Blocked and SHALL NOT return it.

#### Scenario: A person pushed after prepare
- **WHEN** a person pushes to the item branch after `prepare`, and a `premise` request with evidence follows
- **THEN** the lease of the withdraw fails, the item is Blocked and is not returned, and the push of the person stays on the branch

#### Scenario: A branch at its base
- **WHEN** no earlier Job pushed to the item branch, and a `premise` request with evidence follows
- **THEN** the withdraw pushes nothing, and the Status is New

#### Scenario: A publish that runs again after the withdraw
- **WHEN** the withdraw deleted the branch of an earlier Job, and the Job ended before the return
- **THEN** the next `publish` withdraws nothing again and returns the item to New

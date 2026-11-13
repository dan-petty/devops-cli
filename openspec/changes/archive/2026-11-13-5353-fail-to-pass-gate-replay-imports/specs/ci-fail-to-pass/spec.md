## ADDED Requirements

### Requirement: Each gate row run imports the source of its tree
`devops ci fail-to-pass` SHALL start the gate row of each tree with the `src/` of that tree first on the import path. The base run SHALL import `devops_cli` from the `src/` of the base tree, and the head run from the `src/` of the head tree, also when the editable install of the interpreter names the `src/` of another checkout.

#### Scenario: A fix that adds a manifest and lists it in src
- **WHEN** a fix adds `k8s/b.yaml`, names it in a list of `src/`, and changes a check module of a gate row, and a check module that the fix does not change reads that list
- **THEN** the unchanged check module passes on the base tree, the changed case fails on base and passes on head, and the replay is satisfied

#### Scenario: The interpreter names the head source
- **WHEN** the interpreter that runs the command finds `devops_cli` in the `src/` of the head checkout
- **THEN** the gate row run on the base tree still imports `devops_cli` from the `src/` of the base tree

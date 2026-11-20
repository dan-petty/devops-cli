## ADDED Requirements

### Requirement: The manual matcher drifts a tool manual only from a recorded version
The manual matcher SHALL take the version of a tool from the environment facts, which the tool runs of the session record. A manual of a tool with no recorded version, or with the version `unknown`, SHALL match by the name of the tool. A manual SHALL be drift only when the recorded version is outside its range. No pin SHALL give a version.

#### Scenario: Versions of kubectl
- **WHEN** a manual applies to `tool:kubectl@1.*` and the environment holds no version, `unknown`, `1.2.3` and `2.0.0` in turn
- **THEN** the manual matches for the first three, and for `2.0.0` it is drift with the reason `mismatched tool kubectl: requires 1.*, found 2.0.0`

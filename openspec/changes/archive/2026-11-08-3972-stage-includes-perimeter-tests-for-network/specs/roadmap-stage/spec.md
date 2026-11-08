## ADDED Requirements

### Requirement: A manifest plan names the tests that reference it
The stage job SHALL refuse a plan that changes a YAML manifest under `k8s/` and lists no test file that references that manifest, because the implement job cannot edit a test outside the `Changes:` list of the plan.

#### Scenario: The plan of the logging egress rule omits the logging test
- **WHEN** the plan changes `k8s/logging/networkpolicy.yaml`, the job records `tests/commands/k8s/test_k8s_logging_stack.py` as a reference to it, and the plan lists no such test
- **THEN** the problem names `k8s/logging/networkpolicy.yaml` and `tests/commands/k8s/test_k8s_logging_stack.py`, and it asks for the test in `Changes:`

#### Scenario: The plan of the logging egress rule names the logging test
- **WHEN** the plan changes `k8s/logging/networkpolicy.yaml` and lists `tests/commands/k8s/test_k8s_logging_stack.py`
- **THEN** the path gate reports no problem that names either path

#### Scenario: The test builds the manifest path from its parts
- **WHEN** a test file holds the literals `logging` and `networkpolicy.yaml` in separate strings
- **THEN** the record names that test as a reference to `k8s/logging/networkpolicy.yaml`

#### Scenario: The test holds only the folder name
- **WHEN** a test file holds `logging` but not `networkpolicy.yaml`
- **THEN** the record names no reference to `k8s/logging/networkpolicy.yaml` for that file

#### Scenario: The job records no reference
- **WHEN** the gate gets no record, as a replay of a case with none does
- **THEN** the check reports no missing reference

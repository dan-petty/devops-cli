# test-ratchets Specification

## Purpose
The ceilings over the retired test forms, which only fall: string patches of devops-cli names and private imports from devops-cli across the test tree.

## Requirements

### Requirement: The tests hold at most the recorded patches and private imports
`tests/invariants/test_source_tree.py` SHALL hold the count of string patches of `devops_cli` names over all of `tests/` to `_INTERNAL_PATCH_CEILING`, and the count of private imports from `devops_cli` over all of `tests/` to `_PRIVATE_IMPORT_CEILING`. A new patch or a new import SHALL fail the test, and a fix SHALL lower the ceiling in the same pull request.

#### Scenario: A new string patch
- **WHEN** a test file in any directory under `tests/` adds a string patch of a `devops_cli` name
- **THEN** the count passes the ceiling and the test fails

#### Scenario: A new private import
- **WHEN** a test file in any directory under `tests/` imports a private name from `devops_cli`
- **THEN** the count passes the ceiling and the test fails

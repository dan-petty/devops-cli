## Purpose
Tests SHALL exercise product behavior through public interfaces and shared fakes, without patching private names or importing private symbols from devops_cli.

## ADDED Requirements

### Requirement: tests-use-public-interfaces
Tests in the 49-file set SHALL exercise product behavior through public CLI commands and shared fakes from tests/support/fakes/, without patching devops_cli private names or importing names that start with an underscore.

#### Scenario: no-private-patch-or-import
- **WHEN** a test file in the 49-file set is executed
- **THEN** it patches no devops_cli module, class, function or attribute, and imports no name that starts with an underscore from devops_cli

#### Scenario: shared-fake-installed
- **WHEN** a test needs a double for a devops_cli dependency
- **THEN** the double is a shared fake from tests/support/fakes/ installed through its seam or fixture

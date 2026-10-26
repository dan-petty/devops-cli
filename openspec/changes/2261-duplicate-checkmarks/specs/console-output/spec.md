# Spec Delta

## Purpose

Provides formatted and leveled console output for the command-line interface, including level prefixes, styling, and stream routing.

## ADDED Requirements

### Requirement: Leveled print functions format messages without caller prefix duplication

The console output system SHALL format leveled console messages with standard level prefixes. Callers SHALL NOT include the level prefix symbol in the message argument passed to `print_success`, `print_error`, `print_warning`, `print_info`, or `print_step`.

#### Scenario: Success message formatting without duplicated prefix
- **WHEN** `print_success` is called with a success message string
- **THEN** the output stream receives the message prefixed by exactly one check mark symbol

#### Scenario: Leveled print call invariant enforcement
- **WHEN** tests validate source code calls to leveled print functions across `src/devops_cli`
- **THEN** no call passes a string argument that begins with the level prefix symbol of that function

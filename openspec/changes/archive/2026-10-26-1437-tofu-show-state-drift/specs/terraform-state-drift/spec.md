# Spec Delta

## Purpose

How OpenTofu and Terraform state inspection and drift detection execute through CLI JSON interfaces to support encrypted state and modules.

## ADDED Requirements

### Requirement: State inspection reads state through tofu show -json
The state reading implementation SHALL run `tofu show -json` (or `terraform show -json` when OpenTofu is absent) to extract recorded state resources and modules from initialized working directories.

#### Scenario: Initialized directory with child modules
- **WHEN** an initialized directory contains declared modules and `tofu show -json` outputs resources under `child_modules`
- **THEN** state inspection includes all child module resources, and drift detection marks them as in sync rather than orphaned

#### Scenario: Encrypted state backend
- **WHEN** OpenTofu uses client-side state encryption and `tofu show -json` outputs decrypted state
- **THEN** state inspection populates the resources list instead of returning an empty state

### Requirement: Drift detection reads live changes through tofu plan -refresh-only -json
The drift detection command SHALL execute `tofu plan -refresh-only -json` (or `terraform plan -refresh-only -json`) to detect attribute changes against live infrastructure.

#### Scenario: Attribute drift on a declared resource
- **WHEN** `tofu plan -refresh-only -json` reports a `resource_drift` entry for a resource
- **THEN** drift detection marks that resource as drifted and reports drift detected

### Requirement: Uninitialized directory reports state unavailable
When a directory is not initialized with `.terraform`, drift detection SHALL report that state is unavailable and name `tofu init`.

#### Scenario: Running drift on uninitialized directory
- **WHEN** `devops tf drift` runs on a directory lacking a `.terraform` directory
- **THEN** the command warns that state is unavailable and advises running `tofu init`

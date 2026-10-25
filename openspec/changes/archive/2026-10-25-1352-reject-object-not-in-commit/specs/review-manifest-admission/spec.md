# Spec Delta

## Purpose

Validates Kubernetes manifest object locations in review candidate findings against the reviewed revision to prevent findings for non-existent objects.

## ADDED Requirements

### Requirement: Candidate findings citing absent Kubernetes objects are rejected
The review admission gate SHALL reject any candidate finding that cites a Kubernetes object not present in the reviewed revision manifest objects with rejection reason `object-not-in-commit`.

#### Scenario: Candidate finding cites ghost object
- **WHEN** a candidate finding cites a Kubernetes object key that does not exist in the reviewed revision manifest objects
- **THEN** admission returns None and increments rejection reason `object-not-in-commit`

#### Scenario: Candidate finding cites existing manifest object
- **WHEN** a candidate finding cites a Kubernetes object key that exists in the reviewed revision manifest objects
- **THEN** admission validates the object location and proceeds with finding admission

### Requirement: Candidate findings with only a logical location reach validation
The location validator SHALL permit a candidate finding with an empty physical path and a non-empty logical location to reach logical location validation. With no physical region, the finding SHALL be admitted only when a matching manifest object exists as evidence.

#### Scenario: Logical location matches manifest object without physical path
- **WHEN** a candidate finding has an empty physical path and a logical location matching an object in the reviewed manifests
- **THEN** location validation succeeds and admission constructs a finding with the logical location and empty path

#### Scenario: Logical location absent without physical path
- **WHEN** a candidate finding has an empty physical path and a logical location not present in the reviewed manifests
- **THEN** location validation fails with rejection reason `object-not-in-commit`

### Requirement: Manifest reader and scanner adapters build unified object keys
The manifest reader and scanner adapters SHALL build Kubernetes object keys using one canonical format: `Kind/namespace/name` when a namespace is present, and `Kind/name` when no namespace is present.

#### Scenario: Canonical key with namespace
- **WHEN** a manifest document or scanner finding specifies kind, name, and namespace
- **THEN** the constructed key is formatted as `Kind/namespace/name`

#### Scenario: Canonical key without namespace
- **WHEN** a manifest document or scanner finding specifies kind and name without a namespace
- **THEN** the constructed key is formatted as `Kind/name`

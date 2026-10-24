# Spec Delta

## ADDED Requirements

### Requirement: Static security analysis runs golangci-lint on Go files

The review SHALL run golangci-lint for Go files once per nearest go.mod module root and filter findings to reviewed files. Missing binaries or toolchain failures SHALL record non-zero analyzer states instead of zero findings.

#### Scenario: Go files in a module root
- **WHEN** a review runs static analysis on Go source files in a repository with a go.mod file
- **THEN** golangci-lint executes once for the module root and findings are filtered to the reviewed files

#### Scenario: Missing golangci-lint binary
- **WHEN** a review runs static analysis on Go files but the golangci-lint executable is not on PATH
- **THEN** the analyzer state for golangci-lint is recorded as not installed

## ADDED Requirements

### Requirement: A golangci-lint scan reads the Go toolchain and the module cache from go env
Before a golangci-lint scan, the scanner SHALL read the toolchain and the module cache of the host with `go env -json GOROOT GOMODCACHE`, started outside the tree with `GOTOOLCHAIN=local`. A `go env` that fails SHALL give a failed scan that starts no golangci-lint.

#### Scenario: The go env of a scan
- **WHEN** golangci-lint scans a Go module
- **THEN** `go env -json GOROOT GOMODCACHE` starts outside the module with `GOTOOLCHAIN=local`

#### Scenario: A host whose go env fails
- **WHEN** `go env` exits with an error before a golangci-lint scan
- **THEN** the scan fails, starts no golangci-lint, and its reason names `go env`

### Requirement: golangci-lint gets the Go toolchain, the module cache and its caches, and no network
The request of golangci-lint SHALL name the toolchain in `GOROOT`, bind it read-only, and put its `bin` first on the `PATH`. It SHALL name the module cache in `GOMODCACHE` and bind it read-only when it exists. It SHALL name a Go build cache in `GOCACHE` and a golangci-lint cache in `GOLANGCI_LINT_CACHE`, both outside the tree, in `writable_dirs`. It SHALL set `GOPROXY=off` and `GOTOOLCHAIN=local`, SHALL set no `GOFLAGS`, and SHALL select no network profile.

#### Scenario: A scan of a Go module
- **WHEN** golangci-lint scans a Go module on a host whose `go env` names a toolchain and a module cache that exist
- **THEN** the request binds the toolchain and the module cache read-only, names them in `GOROOT` and `GOMODCACHE`, and puts the `bin` of the toolchain first on the `PATH`
- **AND** the request names `GOCACHE` and `GOLANGCI_LINT_CACHE`, two directories outside the module, in `writable_dirs`
- **AND** the request sets `GOPROXY=off` and `GOTOOLCHAIN=local`, sets no `GOFLAGS`, and selects no network profile

### Requirement: A Go module whose modules are not in the module cache is a coverage gap
A golangci-lint run that ends with an error because the `go` command finds a module neither in the module cache nor on a proxy (`module lookup disabled by GOPROXY=off`) SHALL give a coverage gap with no findings. Its reason SHALL name the module cache and `go mod download`. Another error that stops the run SHALL still give a failed scan.

#### Scenario: A host with no module cache
- **WHEN** golangci-lint scans a Go module that requires another module, on a host whose module cache does not exist, and the run ends with `module lookup disabled by GOPROXY=off`
- **THEN** the request binds no module cache
- **AND** the scan reports a coverage gap with no findings, and its reason names the module cache and `go mod download`

#### Scenario: A typecheck error
- **WHEN** the run of golangci-lint ends with a typecheck error
- **THEN** the scan fails, and its reason quotes the error

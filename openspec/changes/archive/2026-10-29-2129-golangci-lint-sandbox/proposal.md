# Proposal

## Why

Issue #2129, part of #772: since #2096, a review runs its tools in a sandbox with no network, a read-only tree and a private HOME. golangci-lint was not proven there. It loads the packages of a module through the `go` command, and in the sandbox:

- `go` is not on the `PATH` when the toolchain is outside `/usr/local/bin`, `/usr/bin` and `/bin`, such as in `/usr/local/go/bin`. A toolchain outside `/usr` is not bound at all.
- The module cache of the host is not bound, and the sandbox has no network to fetch a module.
- The Go build cache and the golangci-lint cache fall in the private HOME, a tmpfs of 64 MiB, and are lost after each run.

## What Changes

- Before a golangci-lint scan, the scanner reads `go env -json GOROOT GOMODCACHE` on the host. `go env` starts in the temporary directory with `GOTOOLCHAIN=local` and the Go variables of the host environment.
- The request of golangci-lint:
  - names the toolchain in `GOROOT`, binds it read-only, and puts its `bin` first on the `PATH`. The `PATH` of the host follows, so the direct executor finds its programs as before;
  - names the module cache in `GOMODCACHE` and binds it read-only, when it exists;
  - names a Go build cache in `GOCACHE` and a golangci-lint cache in `GOLANGCI_LINT_CACHE`. Both are directories of the tree, outside the tree, and the request binds them read-write;
  - sets `GOPROXY=off` and `GOTOOLCHAIN=local`, so the `go` command fetches no module and no toolchain;
  - sets no `GOFLAGS`. The `go` command then uses the `vendor` directory of a module that has one, and otherwise reads `go.mod` and `go.sum` and never writes them (`-mod=readonly`). The issue proposed `GOFLAGS=-mod=mod`, and `## Feasibility` gives the reason that the change does not set it.
- A run that stops because a module is not in the module cache (`module lookup disabled by GOPROXY=off`) is a coverage gap with no findings. Its reason names the module cache and `go mod download`.
- A `go env` that fails gives a failed scan whose reason names `go env`.
- `BaseSecurityScanner` gets two hooks, each empty by default: `tool_env`, the variables that a tool needs besides those of its data and cache directories, and `coverage_gap`, the reason why a run left its targets unscanned for a cause outside the tool.
- The direct executor of `devops scan` gets the same request. So a scan outside a review also fetches no module, and gives the same coverage gap.
- Behavior that a consumer observes changes, so the change carries three ADDED requirements in `review-tool-sandbox`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `review-tool-sandbox`: golangci-lint gets the Go toolchain, the module cache and its caches, and no network. A module whose modules are not in the module cache is a coverage gap.

## Impact

- `src/devops_cli/security/golangci_lint.py`, `src/devops_cli/security/base.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/commands.py`.
- `src/devops_cli/security/ruff.py`: the directory of the cache of a tree moves to `tree_cache_dir` in `base.py`, which golangci-lint uses too. The directory does not change.
- `tests/test_golangci_lint_scanner.py`.
- `SECURITY.md`, item 7.

## Feasibility

- golangci-lint 1.64.6, which `tools.lock` pins, is installed on the host of this change. With no `go` on the `PATH`, `golangci-lint run --out-format sarif` in a small module printed `failed to load with go/packages: err: go command required, not found: exec: "go": executable file not found in $PATH`. It also tried `go env -json GOCACHE GOROOT`. So golangci-lint starts the `go` of the `PATH` (measured on 2026-10-29).
- `GOLANGCI_LINT_CACHE=<dir> golangci-lint cache status` printed `Dir: <dir>`. The variable moves the cache of golangci-lint.
- The documentation of the `go` command (`go help environment`, `go help cache` and the module reference at go.dev/ref/mod):
  - `GOPROXY=off` disallows downloading modules from any source. A module that is not in the cache gives `module lookup disabled by GOPROXY=off`, the text of `errProxyOff` in `cmd/go/internal/modfetch/proxy.go`.
  - `GOTOOLCHAIN=local` runs the bundled toolchain and never downloads another one.
  - `GOCACHE` names the build cache and `GOMODCACHE` names the module cache. The `go` command makes the files of the module cache read-only, and it reads a module that is extracted there without a write.
  - `-mod=mod` makes the `go` command ignore the `vendor` directory and update `go.mod` and `go.sum` when they need a change. The tree in the sandbox is read-only. So `GOFLAGS=-mod=mod`, as the issue proposed, makes a module with a `vendor` directory need the module cache, and makes a run that must update `go.mod` fail on the write. The default of the `go` command (`-mod=vendor` when the `vendor` directory exists, else `-mod=readonly`) needs neither, so the change sets no `GOFLAGS`.
- The sandbox of #2096 binds a read-only directory that a scanner names in `data_dirs` (`ToolDataDir`) and a writable directory that it names in `cache_dirs` (`ToolCacheDir`). Its `PATH` is `/usr/local/bin:/usr/bin:/bin` (`CONST_HOST_SANDBOX_DEFAULT_ENV`), and it binds only `/usr` of the system. A toolchain in `/usr/local/go` is bound but is not on the `PATH`, so the request puts `<GOROOT>/bin` first. A toolchain or a module cache outside `/usr` passes the bind guard of the sandbox unless it holds the home directory or the tree, or passes through a credential directory.
- Not proven on the host of this change: it has no Go toolchain, so golangci-lint did not run in the sandbox. The tests drive the request and the outcome through `ToolExecutorFake` and the process fake.

## Existing Tool Considered

- `go env` names the toolchain and the module cache, with the Go configuration file and the variables of the host. The change builds no reader of the Go configuration file and no parser of `go.mod`.
- The `go` command itself says which module is missing. The change reads its error and does not check the module cache before the run.
- The hooks `data_dirs` and `cache_dirs` of #2096 bind the directories. The change deletes `_ruff_cache_dir`, which `tree_cache_dir` replaces.

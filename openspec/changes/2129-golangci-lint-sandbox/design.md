# Design

## Decisions

### `go env` names the toolchain and the module cache

The scanner starts `go env -json GOROOT GOMODCACHE` once before each scan, on the host. It starts in the temporary directory, so the `go.mod` of no reviewed tree selects another toolchain, and with `GOTOOLCHAIN=local`, so a `GOTOOLCHAIN` of the host fetches no toolchain. The variables of the host that select the toolchain and the cache (`GOROOT`, `GOPATH`, `GOMODCACHE`, `GOENV`, `XDG_CONFIG_HOME`) reach it, so it names the module cache that `go mod download` fills on this host. The scanner keeps the answer for the scan that follows. The answer depends only on the host, so two scans on two threads write the same value.

### The request of golangci-lint

- `data_dirs` gives `GOROOT` and `GOMODCACHE`. The base binds each one read-only when it exists, and names it to the tool by its variable. A host with no module cache gives no `GOMODCACHE`.
- `cache_dirs` gives `GOCACHE` and `GOLANGCI_LINT_CACHE`, in the directory of the tree in the data cache directory, as the Ruff cache is. No tree writes the cache of another tree (#972).
- `tool_env`, a new hook of the base, gives `GOPROXY=off`, `GOTOOLCHAIN=local`, and a `PATH` that starts with `<GOROOT>/bin` and continues with the `PATH` of the host.

### A module that is not in the module cache is a coverage gap

`coverage_gap`, a new hook of the base, reads the run of the tool before the base reads its output. golangci-lint answers with a reason when the run ended with an exit code that is not zero and its standard error holds `module lookup disabled by GOPROXY=off`. The scan is then a coverage gap with no findings. The reason names the module cache and `go mod download`.

## Rejected alternatives

- **`GOFLAGS=-mod=mod`, as the issue proposed.** The `go` command then ignores a `vendor` directory and writes `go.mod` and `go.sum` when they need a change. The tree in the sandbox is read-only, so the write fails, and a vendored module needs a module cache that it does not need with the default (go.dev/ref/mod, "Build commands").
- **Find the toolchain and the cache from the variables of the host.** `GOMODCACHE`, else the first entry of `GOPATH` with `pkg/mod`, else `$HOME/go/pkg/mod`, misses a value that `go env -w` wrote to the Go configuration file. `go env` reads both.
- **Check the module cache before the run.** That needs a parser of `go.mod` and a copy of the layout of the module cache, or a second tool run (`go mod edit -json`, `go list -m all`) on the untrusted tree. The `go` command already stops with the name of the missing module.
- **Read the error from the reason of the failed scan.** `masked_reason` cuts a reason at 256 characters (`CONST_MAX_ERROR_DETAIL_LENGTH`). golangci-lint puts the error of the `go` command after about 200 characters of its own text, so a module path of normal length pushes the marker out of the reason.
- **One Go build cache for every tree.** A tool that a reviewed tree breaks could write entries that the review of another tree then reads. The Ruff and mypy caches have one directory for each tree for the same reason (#972).
- **The `PATH` of the sandbox policy after the toolchain.** The direct executor starts the tool with the environment of the request, so a `PATH` with only system directories would lose the programs of the host, such as the golangci-lint that `devops install-tools` puts in `~/.local/bin`. In the sandbox, a directory of the host `PATH` that the sandbox does not bind does not exist.

# Design

## Decisions

- **The doctor collects the kubectl version.** `collect` reads `kubectl version --client -o json` once, and `diagnose` reads the snapshot, so the rules stay pure. `deploy-stack` reads the same function. With no answer, the skew rule of kubectl gives no finding.
- **The record of a run holds the version.** The analysis, the knowledge base and the profile read the versions that the tool runs recorded. A tool that did not run has no version, so a knowledge base manual of that tool is drift.
- **No `--version` run in the record path.** The canary and the tool executor record the version of the installed distribution of the tool, else `unknown`. They do not start a native tool with `--version` outside the sandbox. The digest of the binary names it exactly.
- **The profile hashes the runs.** `tool_versions_digest` covers the tool, the version and the binary digest of each run, so a new Semgrep gives a new digest and a change of `tools.lock` alone gives none.
- **The rule pack test returns the version.** `run_rule_pack_tests` returns the lock and the version of the Semgrep that ran, so the command prints it.
- **The live OpenSpec replay compares the runs and their exit codes.** The text of a run holds the time of the run, so the test does not compare it.

## Rejected alternatives

- `path_version` for a native tool in the record path: it starts the tool outside the sandbox at each run, and the floor of the test suite refuses such a start.
- Delete `research/tool_pins.py`: `devops research advisories` reads the binaries of `tools.lock` through it while the installer still installs them, and #6409 extends the module with the root `package-lock.json`. #4363 removes it with the lock.
- Keep a pin as the fallback version: the owner decision of 2026-11-19 forbids a pin as a source.

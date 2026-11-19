# Design

## Decisions
- The Style Dictionary lock is clean under `npm audit` with `glob` 14.0.2 and `minimatch` 11.0.1, so the lock needs no `.npm-audit-ignore.yaml` entry.
- The entry is `[npm.style-dictionary]` at 5.8.0, the version that the lock and `package.json` already name.
- The Design Tokens job installs the tool with `devops install-tools --tool style-dictionary`, the same path as OpenSpec, and drops the hand `npm ci` step.

## Rejected alternatives
- Switch the `audit` row to `osv-scanner` with an `IgnoredVulns` entry, as the issue proposed: #6205 already gave `npm audit` a time-limited ignore file, and SECURITY.md forbids turning off a scanner.
- Keep the lock outside `tools.lock`: the `audit` row would not scan it and `devops install-tools` would not install it.
- Add a time-limited ignore for `glob` and `minimatch`: a fixed release exists for each, and SECURITY.md prefers the fix.

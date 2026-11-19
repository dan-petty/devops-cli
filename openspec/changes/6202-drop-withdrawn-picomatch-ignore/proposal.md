# Proposal: #6202

## Why

`.npm-audit-ignore.yaml` ignores GHSA-fc5q-39xc-vjpf (picomatch ReDoS) in the OpenSpec lockfile until 2026-11-20, because no released picomatch fixes it (#6202). GitHub withdrew the advisory on 2026-11-18. The picomatch maintainer says that the pattern is not a vulnerability. `npm audit` of the OpenSpec lockfile now reports no finding, so the ignore entry has no finding to ignore. SECURITY.md "A Finding with No Fix" applies only while a scanner names the finding.

## What Changes

- Remove the GHSA-fc5q-39xc-vjpf entry from `.npm-audit-ignore.yaml`. The file keeps its header and an empty `vulnerabilities` list, so the next entry has its place and form.
- Keep picomatch 4.0.7 in the OpenSpec lockfile. No newer picomatch release exists, and the withdrawn advisory names no fixed version.
- The change alters only data of a config file. No devops command, option, message or manifest changes, so the change has no spec delta (skip_specs: true). The requirements of `ci-dependency-audit` stay true.

## Capabilities

None. The change has no spec delta.

## Impact

The `audit` row of `devops ci` and `devops ci audit` read no entry for GHSA-fc5q-39xc-vjpf. After 2026-11-20 the audit prints no note of an expired entry. The change fits one pull request.

## Feasibility

Read on 2026-11-19:

- `devops gh api /advisories/GHSA-fc5q-39xc-vjpf`: `withdrawn_at` 2026-11-18T15:38:56Z, vulnerable range `<= 4.0.7`, no first patched version.
- `npm view picomatch versions --json`: the newest release is 4.0.7 (2026-08-24). No release holds a fix, so a bump is not possible.
- `npm ls --package-lock-only picomatch` in `src/devops_cli/tools_lock/openspec`: `@fission-ai/openspec@2.1.0` and `tinyglobby@0.2.17` (through `fdir@6.5.0`) pull picomatch 4.0.7.
- `npm audit --package-lock-only --json` of the OpenSpec lockfile: 0 vulnerabilities.

The premise of the issue (bump picomatch to a fixed release) fails, because the advisory is withdrawn and no fix will come. The re-scope keeps the goal of the issue: the repository holds no ignore entry for GHSA-fc5q-39xc-vjpf, and the audit passes.

## Existing Tool Considered

`npm audit` is the open, maintained tool that reports the finding, and `devops ci audit` already reads its report. The change builds no code and deletes one data entry. It deletes no internal code.

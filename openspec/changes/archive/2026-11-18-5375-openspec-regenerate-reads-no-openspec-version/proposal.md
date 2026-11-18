# Proposal: #5375

## Why

`devops openspec regenerate` runs `openspec update --force` with the binary that PATH finds, and it
reads no version (`src/devops_cli/commands/openspec.py:51`). A binary older than the tools lock pin
then writes its own skill text into the working tree. The `openspec-gate` pre-commit hook refuses
the commit of that text, but the tree is already changed, so the user must restore the skill files
from git. The version guard that #5355 added to the gate (`version_finding`,
`src/devops_cli/openspec/gate.py:111`) is present, and `regenerate` does not call it. The risk grows
with #5078, which moves the pin to OpenSpec 2.0.0 and a new skill layout: a 1.x binary that stays
first on PATH then writes the old layout. Closes #5375.

## What Changes

- The gate's version guard becomes the public `version_finding`, which `check_openspec` and
  `regenerate` both call.
- `regenerate` reads the version before it writes and raises a `ToolExecutionError` (exit 1) when
  the binary prints another version than the lock's or prints no version. The error names the path,
  the printed version, the locked version and the install hint.
- A dry run still writes nothing and runs no `--version` and no `openspec update --force`.

## Capabilities

`openspec-regenerate` (new): `devops openspec regenerate` reads the version of the binary on PATH
before it writes a skill.

## Impact

- An older binary on PATH changes no skill file, and the message says how to install the pinned one.
- A binary that prints the locked version regenerates as before.
- The change fits one pull request.

## Feasibility

- Read 2026-11-18: `version_finding` reads `openspec --version` through `OpenSpecTool.run` with the
  isolated environment and the tool timeout, and `check_openspec` returns its finding before its
  other checks (`src/devops_cli/openspec/gate.py:111`). `regenerate` runs
  `regenerate_skills(tool, root)` inside `isolated_openspec()` (`src/devops_cli/commands/openspec.py:51`),
  so one call before it covers the write. The tools lock pins `openspec` 2.1.0
  (`src/devops_cli/tools_lock/tools.lock:600`).

## Existing Tool Considered

The alternatives check of 2026-11-17 recorded verdict none and no tool. The guard of the gate that
#5355 added covers the need, and this change reuses it as `version_finding`; it builds no new check.

# Task: OpenSpec Is Evaluated and Not Adopted as the Change-Proposal Layer (#1753)

**Issue**: [#1753](https://github.com/dan-petty/devops-cli/issues/1753)
**Scope**: scope/ci
**Feasibility**: OpenSpec 1.14.3 was read from the npm registry (`npm view`, `npm audit signatures`), the GitHub API (repository, contributors, commits, releases) and the published tarball (`dist/telemetry/`, `dist/core/version-check.js`, `dist/core/config.js`, `package.json`). It was installed with `--ignore-scripts` and run only in scratch directories under `/tmp`, with `HOME` and `XDG_CONFIG_HOME` inside the scratch tree and `DO_NOT_TRACK=1`, `OPENSPEC_TELEMETRY=0` and `OPENSPEC_NO_UPDATE_CHECK=1` set, so no event was sent and no anonymous id was created. The trial re-specified the delivered item #1805 as a change, validated and archived it, then merged two archived changes to one capability (conflict) and two unarchived ones (clean). The repository side was read from `src/devops_cli/commands/pr.py`, `src/devops_cli/roadmap/close.py`, `src/devops_cli/config/constants.py`, `tests/test_agent_task_files.py`, `tools.lock`, `.gitignore` and `.devcontainer/devcontainer.json`.

## Description

ADR 0009 answers the issue's questions 1-5 with the sources and measurements above, records the trial of #1805 with its effort and friction, and decides to reject OpenSpec for now. The health of the project is not the reason (MIT, weekly releases, signed and attested packages): a change folder repeats what the issue and the task file hold, its propose-then-apply lifecycle clashes with the rule that a task file is written by the delivering pull request as it will read merged, archive conflicts when two changes touch one capability, the Node tool needs a pinning path `tools.lock` does not have, and replacing task files means rewriting the readiness check, the closing comment and their tests. The ADR lists what an adoption would have rewritten and when to revisit, chiefly if #1750 keeps per-change records in the repository and wants a proposal reviewed before its code.

## Acceptance Criteria

- [x] Questions 1-5 are answered in ADR 0009 with sources: the npm registry, the GitHub repository and its releases, the license, and the 1.14.3 tarball.
- [x] One trial change is recorded in ADR 0009 with its effort (files and words against #1805's task file and fragment) and its friction.
- [x] ADR 0009 states reject, and that AGENTS.md, readiness and the task-file tests do not change, with the files an adoption would have rewritten.
- Pending a person: confirm the decision when merging. To adopt or adapt instead, file the migration issues, each delivered by one pull request, with `devops roadmap intake --title "<title>" --body-file <file> --confirm` (a person runs it while `roadmap-service` is suspended, #1562).

## Deliverables

- [x] `docs/adr/0009-openspec-is-not-adopted-as-the-change-proposal-layer.md`.
- [x] `changelog.d/1753.md`.
- Revisiting OpenSpec if #1750 keeps per-change records in the repository: decided with #1750, which is not part of this item.

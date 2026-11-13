# AGENTS.md — devops-cli

> **Canonical Source**: [CLAUDE.md](./CLAUDE.md), [GEMINI.md](./GEMINI.md) and [.github/copilot-instructions.md](./.github/copilot-instructions.md) point to this file. Each rule lives in one document only.

## Rules for every task

1. **One issue, one pull request.** Work on a topic branch from `origin/main`. Never commit or push to `main`.
2. **Check the premise first.** Confirm it against the real system: upstream documents, source or command output. If newer issues or code replace the item, close it as not planned. If it cannot be built as written, write no compensating code: return it with the evidence and stop. Stop also when you swallow an error, make product code detect tests, or put a second fix on a fix.
3. **Use an open tool before you build.** Name the tool or library that covers the need. To build instead, write the cost in tokens and time. This rule outranks every other convention.
4. **Test new behavior first.** Prove other changes with a command.
5. **Pass the checks.** Never use `--no-verify`. Never lower a security or quality threshold; only the owner can allow it ([exceptions](SECURITY.md#a-finding-with-no-fix)). A check that averages over 5 min + 1 min tolerance is a P0 bug.
6. **Open every pull request as a draft** with `devops pr create`, and mark it ready only after the checks pass.
7. **Use `devops gh` and `devops pr`.** Never run bare `gh`. Run one `devops ai` call at a time, only when no file or deterministic check can answer ([ask-jev](.agents/skills/ask-jev/SKILL.md)).
8. **Write as merged.** Make no commit or pull request that only updates tracking. If a change makes a document wrong, fix it in the same pull request.
9. **Write prose in ASD-STE100** ([rules](src/devops_cli/ai/tasks/style_ste100.md)).
10. **Keep private data out of the repository.** Never commit a secret, a gitignored file, an internal hostname, a private address or registry, or a device path. Use `example.com`, RFC 5737 and `<storage-node>`.
11. **Fix the cause** at its source. If an outside constraint blocks the fix, add a check that fails if the problem returns. Comment on the open issue of each problem that you find, else file one.
12. **Keep your own files out of git.** Put agent files under `.data/agent/` and scratch scripts under `.data/agent/scratch/`. Back up a file outside the workspace before you edit it. Never change `config.yaml`.
13. **Keep tool output small.** Search before you read, and read only the lines you need. Ask each command for less output: `git diff --stat`, `--jq`, `--limit`, a Loki `limit`. Keep each necessary fact: error lines, `file:line`, failed test IDs.

**Only a person** merges pull requests, records verdicts, plans milestones and changes secrets, repository settings and hardware. Agents run every other project command, but no release step.

## Where to look

| When you | Read |
| --- | --- |
| look up a setting, error, metric or command | [README](README.md), [commands](docs/CLI_REFERENCE.md) |
| set up, name a branch or a pull request, run one check | [contributing](CONTRIBUTING.md) |
| write or change a test | [testing](docs/TESTING.md) |
| write code: errors, subprocesses, HTTP, models, prompts, constants | [architecture](ARCHITECTURE.md), [contributing](CONTRIBUTING.md) |
| style an artifact | [design](docs/DESIGN.md) |
| handle secrets, egress, private data, sandboxes or telemetry | [security](SECURITY.md) |
| take an issue to release, or a pull request to merge | [roadmap](docs/ROADMAP_WORKFLOW.md), [SDLC](docs/SDLC.md) Phase 6 |
| plan an item as an OpenSpec change | [config](openspec/config.yaml) |
| file an issue | `devops roadmap intake` ([bug](.github/ISSUE_TEMPLATE/bug_report.yml), [feature](.github/ISSUE_TEMPLATE/feature_request.yml)) |
| run a routine task or audit | [routines](docs/ROUTINE_TASKS.md) |
| use a project term or a decision record | [terms](CONTEXT.md), [ADRs](docs/adr/) |
| run a review or work on verdicts | [reviews](docs/SELF_IMPROVEMENT.md) |
| change a manifest, the cluster or OpenTofu | [k8s](k8s/README.md), [cluster](docs/CLUSTER.md), [tf](tf/README.md) |
| learn a subsystem, library or tool | [knowledge base](src/devops_cli/ai/knowledge_base/README.md) |

# AGENTS.md — devops-cli

devops-cli is a Python command-line tool, `devops`, that automates workstation, GitHub, Kubernetes and code-review work. It is alpha before `1.0.0`: a change removes the old path and adds no shim.

> **Canonical Source**: This file is the single source of truth for AI agent instructions. [CLAUDE.md](./CLAUDE.md), [GEMINI.md](./GEMINI.md) and [.github/copilot-instructions.md](./.github/copilot-instructions.md) are pointers to this file. Each rule lives in one document only.

## Rules for every task

1. **One issue, one pull request.** Work on a topic branch from `origin/main`, rebase it before each push, and open one pull request into `main` that closes it (`Closes #<issue>`). Plan it as `openspec/changes/<issue>-<slug>/` and archive it in the last commit with `uv run devops openspec archive <change>`. The title is a Conventional Commit with no `!` before `1.0.0`. Never commit to `main`.
2. **Check the premise first.** Confirm it against the real system: upstream documents, source or command output. Record how in the proposal `## Feasibility` section. If the item cannot be built as written, write no compensating code. Return it to `New` with the evidence (`devops roadmap return`) and stop. Close issues as rejected if their functionality has been superseded by newer issues or code changes. Stop also when you swallow an error, make product code detect tests, or put a second fix on a fix.
3. **Use an open tool before you build.** Name the tool or library that covers the need. To build instead, write the cost in the issue or pull request: tokens to build, keep and fix it, and elapsed time. This rule outranks every other convention.
4. **Test new behavior first** ([docs/TESTING.md](docs/TESTING.md)). Prove other changes with a command. A fix pull request cites its `fail-to-pass` run (`devops ci fail-to-pass --base <ref>`).
5. **Pass the checks.** The pre-push hook runs the fast static checks. Never use `--no-verify`. The required CI checks gate the merge. Never lower a security or quality threshold; only the owner can allow it ([SECURITY.md](SECURITY.md#a-finding-with-no-fix)). A check that averages over 5 min + 1 min tolerance is a P0 bug.
6. **Open every pull request as a draft** with `devops pr create`, watch it with `devops pr monitor <pr_number>`, and mark it ready (`devops pr ready <pr_number>`) only after the checks pass. Reply in each review thread (`devops pr threads reply`). Advance your pull requests oldest first. Never request a Copilot review.
7. **Use `devops gh` and `devops pr`.** Never run bare `gh`: `devops` paces each request against the rate limit.
8. **Write as merged.** Write code and documents as they will read after the merge. Make no commit or pull request that only updates tracking. If a change makes a document wrong, fix it in the same pull request.
9. **Write prose in ASD-STE100** ([rules](src/devops_cli/ai/tasks/style_ste100.md)) for replies, pull requests, issues, commits, documents, prompts and output. Do not hard-wrap text that a program emits.
10. **Keep private data out of the repository.** Never commit a secret, a gitignored file, an internal hostname, a private IP address, a private registry or a device path. Use `example.com`, RFC 5737 addresses and roles like `<storage-node>` ([SECURITY.md](SECURITY.md)).
11. **Fix the cause** at its source. If an outside constraint blocks the fix, add a check that fails if the problem returns. When a `devops` command fails or warns, comment on a matching issue, else file one. File other problems the same way.
12. **Keep your own files out of git.** Put agent files under `.data/agent/` and scratch scripts under `.data/agent/scratch/`. Back up a file outside the workspace to `<path>.bak-<YYYYMMDD-HHMMSS>` before you edit. Never change `config.yaml`.
13. **Use a decision model for a closed choice, a generative model for text.** Ask Jev (`devops ai ask-jev`, skill [`ask-jev`](.agents/skills/ask-jev/SKILL.md)) for yes/no, one option or a rubric on short evidence. It writes no text and does not read a long document. Run one `devops ai` call at a time, only when no file or deterministic check can answer.
14. **Keep tool output small.** Search before you read, and read only the lines you need. Ask each command for less output: `git diff --stat`, `--jq`, `--limit`, a Loki `limit`. Do not remove a fact that the reader needs: error lines, `file:line`, failed test IDs.

**Only a person** merges pull requests (`release-merge.yml` merges the release pull request), records verdicts, plans milestones and changes secrets, repository settings and hardware. Agents run every other project command but no release step: release-please writes `CHANGELOG.md`, manifests and version lines, and agents change the release workflow only by ordinary pull requests ([RELEASE_CYCLE.md](RELEASE_CYCLE.md)). Intake sets the priority label, so set no milestone or priority.

## Where to look

| When you | Read |
| :--- | :--- |
| look up a setting, variable, error code, metric or command | [README.md](README.md), [commands](docs/CLI_REFERENCE.md) |
| set up, name a branch, write a pull request title, run one check, change a command | [CONTRIBUTING.md](CONTRIBUTING.md) |
| write or change a test | [docs/TESTING.md](docs/TESTING.md) |
| write code: errors, subprocesses, HTTP, models, prompts, constants | [ARCHITECTURE.md](ARCHITECTURE.md), [CONTRIBUTING.md](CONTRIBUTING.md) |
| style an artifact | [docs/DESIGN.md](docs/DESIGN.md) |
| handle secrets, egress, private data, sandboxes or telemetry | [SECURITY.md](SECURITY.md) |
| take an issue to release, or a pull request to merge | [roadmap](docs/ROADMAP_WORKFLOW.md), [docs/SDLC.md](docs/SDLC.md) Phase 6 |
| plan and record each item as an OpenSpec change | [openspec/config.yaml](openspec/config.yaml) |
| file an issue | `devops roadmap intake`, in the shape of [bug_report.yml](.github/ISSUE_TEMPLATE/bug_report.yml) or [feature_request.yml](.github/ISSUE_TEMPLATE/feature_request.yml) |
| run a routine task or audit | [docs/ROUTINE_TASKS.md](docs/ROUTINE_TASKS.md) |
| use a project term, or need the reason for a decision | [CONTEXT.md](CONTEXT.md), [docs/adr/](docs/adr/) |
| run a review, or work on verdicts | [docs/SELF_IMPROVEMENT.md](docs/SELF_IMPROVEMENT.md) |
| change a manifest, the cluster or OpenTofu | [k8s](k8s/README.md), [cluster](docs/CLUSTER.md), [tf](tf/README.md) |
| learn a subsystem, library or tool | [knowledge base](src/devops_cli/ai/knowledge_base/README.md) |

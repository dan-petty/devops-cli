# AGENTS.md — devops-cli

devops-cli is a Python command-line tool, `devops`, that automates workstation, GitHub, Kubernetes and code-review work. It is alpha software before `1.0.0`: it keeps no backward compatibility, so a change removes the old path and adds no shim.

> **Canonical Source**: This file is the single source of truth for AI agent instructions. [CLAUDE.md](./CLAUDE.md), [GEMINI.md](./GEMINI.md) and [.github/copilot-instructions.md](./.github/copilot-instructions.md) are pointers to this file. It holds the rules for every task and sends each kind of task to the document that owns it. Each rule lives in one document only.

## Rules for every task

1. **One issue, one pull request.** Work on a topic branch from `origin/main`. Open one pull request into `main` that closes its one issue (`Closes #<issue>`). Plan the item as the change folder `openspec/changes/<issue>-<slug>/`, and archive it in the last commit with `uv run devops openspec archive <change>`. The title is a Conventional Commit. Before `1.0.0`, a title has no `!` and no `BREAKING CHANGE:`. Never commit to `main`.
2. **Check the premise first.** Confirm it against the real system: upstream documents, library source or command output. Record how in the proposal's `## Feasibility` section. If the item cannot be built as written, write no compensating code. Return it to `New` with the evidence (`devops roadmap return <issue> --comment "<evidence>" --confirm`), and stop. Close issues as rejected if their functionality has been superseded by newer issues or code changes. Stop also when you swallow an error, make product code detect tests, or put a second fix on a fix.
3. **Use an open tool before you build.** Name the tool or library that covers the need. To build instead, write the cost in the issue or pull request: tokens to build, keep and fix it, and elapsed time. This rule outranks every other convention.
4. **Test new behavior first** ([docs/TESTING.md](docs/TESTING.md)). Prove any other change with a command. A fix pull request cites its `fail-to-pass` run (`devops ci fail-to-pass --base <ref>`).
5. **Pass the checks.** The pre-push hook runs the fast static checks. Never use `--no-verify`. The required checks of CI gate the merge. Run the full `uv run devops ci` by hand if you want it before a push. Never lower a security or quality threshold: only the owner can allow it. A build or check that averages more than 5 minutes is a P0 bug.
6. **Open every pull request as a draft** with `devops pr create`. Watch it with `devops pr monitor <pr_number>`. Mark it ready with `devops pr ready <pr_number>` only after the checks pass. Reply to each review comment in its thread (`devops pr threads reply <thread_id> "<body>"`). Advance your pull requests, the oldest first. Copilot reviews only when a person asks.
7. **Use `devops gh` and `devops pr` for GitHub.** Never run bare `gh`: the devops commands pace each request against the rate limit.
8. **Write as merged.** Write code, documents and records as they will read after the merge. Make no commit or pull request that only updates tracking. If your change makes a document wrong, fix that document in the same pull request.
9. **Write prose in ASD-STE100** ([rules](src/devops_cli/ai/tasks/style_ste100.md)): replies, pull request, issue and commit text, documents and output strings. Do not hard-wrap text that a program emits.
10. **Keep private data out of the repository.** Never commit a secret, the content of a gitignored file, an internal hostname, a private IP address, a private registry or a device path. Use `example.com`, RFC 5737 addresses and roles such as `<storage-node>` ([SECURITY.md](SECURITY.md)).
11. **Fix the cause** at its source. If an outside constraint blocks the fix, add a check that fails if the problem returns. When a `devops` command fails or warns, check open issues; comment on a match, else file it with `devops roadmap intake --title "fix(<scope>): <summary>" --body-file <file> --confirm`. File other problems and ideas the same way.
12. **Keep your own files out of git.** Put agent files under `.data/agent/` and scratch scripts under `.data/agent/scratch/`. Back up a file outside the workspace to `<path>.bak-<YYYYMMDD-HHMMSS>` before you edit it. Never change `config.yaml`.
13. **Run one `devops ai` call at a time,** and only when a file or a deterministic check cannot give the answer.

**Only a person** merges pull requests, records review verdicts, plans milestones, and changes secrets, repository settings and hosts. Intake sets the priority label of a new issue, so set no milestone or priority on it. release-please makes every release from `main` and writes `CHANGELOG.md`, manifests and version lines, so nobody edits those by hand. Agents change the release workflow and its configuration through ordinary pull requests ([RELEASE_CYCLE.md](RELEASE_CYCLE.md)).

## Where to look

| When you | Read |
| :--- | :--- |
| look up a setting, variable, error code, metric or command | [README.md](README.md) |
| set up, name a branch, write a pull request title, run one check, change a command | [CONTRIBUTING.md](CONTRIBUTING.md) |
| write or change a test | [docs/TESTING.md](docs/TESTING.md) |
| write code: errors, subprocesses, HTTP, models, prompts, constants | [ARCHITECTURE.md](ARCHITECTURE.md), [CONTRIBUTING.md](CONTRIBUTING.md) |
| handle secrets, egress, private data, sandboxes or telemetry | [SECURITY.md](SECURITY.md) |
| take an issue to release, or a pull request to merge | [docs/ROADMAP_WORKFLOW.md](docs/ROADMAP_WORKFLOW.md), [docs/SDLC.md](docs/SDLC.md) Phase 6 |
| plan and record the item a pull request delivers, as an OpenSpec change | [openspec/config.yaml](openspec/config.yaml) |
| file an issue | `devops roadmap intake`, in the shape of [bug_report.yml](.github/ISSUE_TEMPLATE/bug_report.yml) or [feature_request.yml](.github/ISSUE_TEMPLATE/feature_request.yml) |
| run a routine task or audit | [docs/ROUTINE_TASKS.md](docs/ROUTINE_TASKS.md) |
| use a project term, or need the reason for a decision | [CONTEXT.md](CONTEXT.md), [docs/adr/](docs/adr/) |
| run a review, or work on verdicts and suppressions | [docs/SELF_IMPROVEMENT.md](docs/SELF_IMPROVEMENT.md); review guards are in `.devops/review.md` |
| change a manifest, the cluster or OpenTofu | [k8s/README.md](k8s/README.md), [tf/README.md](tf/README.md) |
| learn a subsystem, library or tool | [knowledge base](src/devops_cli/ai/knowledge_base/README.md), `devops <command> --help` |

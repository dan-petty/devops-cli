---
status: proposed
date: 2026-11-21
decision-makers: [owner]
issue: 6601
tracker: 3702
---

# Roadmap steps run their agent apart from the App key

## Context and Problem Statement

The implement Job and the fix-checks Job run the shell of an agent in the runner container, next to the private key of the GitHub App ([ADR 0015](0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md)). The process hardening of #2667 keeps the environment and the memory of the Job from a child, but an agent that writes the git settings, a hook or a build file of the clone can still reach a later call that holds the token. #2695 studied the options with a critic. On 2026-11-20 the owner chose a sequential split of one run into three trust zones (#2695, #3702).

## Considered Options

- **A sandbox command server for the agent shell** (#3694): rejected, because it keeps the agent and the key in one pod.
- **Three phases in sequence, with the outputs of the agent read as data**, the pattern of GitHub Agentic Workflows safe outputs, Codex cloud and the Copilot cloud agent: chosen.
- **A git bundle from the agent**: rejected, because a bundle carries refs, tags, history and authors.

## Decision Outcome

A roadmap step that runs an agent runs three phases, one after the other (`src/devops_cli/roadmap/phases/`):

- **`prepare`** holds the App key and runs no agent code: the GitHub reads, the claim check and a plain full clone of the repository on GitHub in a folder that is new to the run, switched to the issue branch, with git and GitHub calls only. The clone holds no credential.
- **`agent`** holds the model key only and makes no GitHub call. It runs the agent and its checks in the clone, and writes a patch with fixed format flags, an outcome and a summary.
- **`publish`** holds the App key. It reads the state file and the outputs of the agent as data: no link, no FIFO, a size limit, and only the enums and the numbers of the outcome, with each text masked and fenced. It takes the target of the push from GitHub alone: the head branch and the judged head of the pull request, the bot of the App, the workflow files that the merged plan names on the default branch, and the failed check by the name that GitHub gives. It pushes only to the repository on GitHub. A round that `prepare` ends gets its report from `prepare`. It applies each patch with `git apply --index` in a new repository, refuses a new or changed link, gitlink or `.gitmodules` and a workflow file that the plan does not name, and writes one commit with the bot as author for each patch. It checks the claim again right before the push, pushes with a lease on the old tip, and makes the GitHub writes of the outcome.

The fix-checks Job is the first step on the phases (#6601). `--phase all` runs the three phases in one process, so the current Job template keeps working, and keeps the state of `prepare` in memory. The agent phase refuses to start with the App key or a GitHub token in its environment. The implement Job follows (#3702, part C), and stage uses `publish` (#6528). #3700 runs each phase in its own container.

### Addendum: plain git (#6655, 2026-11-21)

The owner asked for a plain issue-branch flow ("it should be relatively straight forward to work an issue branch", #3702 comment 7065393209). The phases use git as a developer does: a full clone, `git switch`, `git apply --index`, `git commit` and `git push --force-with-lease`, with no `read-tree`, `write-tree` or `commit-tree` and no git folder that shares the objects of another. Until #3700, the git calls of `prepare` and `publish` read no global or system configuration, because the home folder is shared with the agent in `--phase all`. No new git hardening comes before #3700.

### Consequences

- An agent that writes the settings of its clone reaches no call with the token: `publish` reads no file of the clone and runs no program of the agent.
- `publish` writes one commit of the bot for each patch. The commits of the fixers stay in the agent clone.
- Until #3700, one process mints one token for the three phases, so the token keeps `workflows: write`. `publish` refuses a workflow file that the merged plan does not name.

### Confirmation

- `tests/roadmap/phases/test_roadmap_phase_publish.py`: one commit of the bot, the lease, and the refusal of each hostile patch.
- `tests/roadmap/steps/test_roadmap_step_fix_checks.py`: the phases on a run folder, the claim before the push, and a fixer that rewrites the state file.
- `tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`: `prepare` starts git only and leaves no credential in its clone.

## More Information

- The tracker: #3702. The design study: #2695. The first step: #6601. The three containers: #3700.
- The specs: `openspec/specs/roadmap-phases/spec.md` and `openspec/specs/roadmap-fix-checks/spec.md`.

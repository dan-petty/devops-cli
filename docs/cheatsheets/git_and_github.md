# Git & GitHub Tool Cheatsheet

Compare native `git` and `gh` (GitHub CLI) commands with unified `devops-cli` workflows across multi-repo workspaces, release branches, and PR governance.

---

## 1. Multi-Repository Workspace Management

| Action / Goal | Original Command (`git` / shell) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **List All Cloned Repos** | `find . -name .git -type d` | `devops repos list` | Auto-detects workspace layout, branch names, and clean/dirty statuses in a formatted table. |
| **Workspace Git Status** | `for d in repos/*; do (cd $d && git status -s); done` | `devops repos status` | Concurrently inspects all local repos, tracking uncommitted changes, staged files, and untracked files. |
| **Sync / Pull All Repos** | `for d in repos/*; do (cd $d && git pull --rebase); done` | `devops repos sync` | Concurrently fetches and rebases upstream branches across all workspace repositories. |
| **Clone New Repository** | `cd repos && git clone <url>` | `devops repos clone <url>` | Automatically normalizes organization directory structure and registers repo in workspace index. |

---

## 2. Branch Hierarchy & Release Governance

| Action / Goal | Original Command (`git`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **List Workspace Branches** | `git branch -a` | `devops branches list` | Displays upstream tracking, ahead/behind commits, and active release branch context. |
| **Create Topic Branch** | `git checkout -b feat/my-feature` | `devops branches create feat/my-feature` | Ensures branch is created off the current active release branch (`release/vX.Y.Z`) per project rules. |
| **Clean Merged Branches** | `git branch --merged \| grep -v "\*" \| xargs -n 1 git branch -d` | `devops branches cleanup` | Safe automated pruning of merged local topic branches without touching protected branches. |

---

## 3. GitHub Pull Request & CI Quality Gate Monitoring

| Action / Goal | Original Command (`gh`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Create Release-Targeted PR** | `gh pr create --base release/v0.1.12 --head feat/my-feature` | `devops pr create --title "feat: ..." --body "..."` | Auto-detects active release branch target, generates changelog summary, and verifies pre-commit hooks. |
| **Inspect Active PR Status** | `gh pr status` | `devops pr status` | Summarizes open PRs, base branches, review requests, and merge readiness. |
| **Monitor Remote CI Checks** | `gh pr checks <pr_number>` / `gh run watch <run_id>` | `devops pr checks <pr_number>` | Live terminal polling and failure diagnosis with direct error snippet highlighting. |
| **View PR Diffs** | `gh pr diff <pr_number>` | `devops pr diff <pr_number>` | Sanitizes prompt boundary tags and strips binary lockfile blobs for clean code review. |

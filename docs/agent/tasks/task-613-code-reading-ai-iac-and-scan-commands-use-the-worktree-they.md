# Task 613: Code-Reading AI, IaC and Scan Commands Use the Worktree They Run In

**Issue**: [#613](https://github.com/dan-petty/devops-cli/issues/613)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

#582 moved the verifying commands onto the worktree they run in. Commands that read, index or
deploy the current tree still used the top-most root, so from a worktree nested inside the
main checkout (such as `.claude/worktrees/<name>`) they acted on the main checkout:
- `devops ai repomap` mapped the main checkout's `src/`;
- `devops ai diagram arch` listed the main checkout's packages;
- `devops ai ast graph` came back empty, because the main checkout's `.gitignore` excludes
  `.claude/` and so marked every worktree file ignored;
- `devops review auto-fix` reported `TARGET_FILE_NOT_FOUND` for files only the worktree has;
- `devops tf` deploys ran `tofu init` and `apply` in the main checkout's `tf/<provider>`;
- Kube-linter findings carried a `.claude/worktrees/<name>/` prefix.

### Key Deliverables Completed:

- [x] **Current-worktree readers**: `ai/repomap.py`, `ai/diagram.py`, `ai/ast/graph.py` (whose
  unreachable fallback is removed), `ai/review/auto_fix.py`, `commands/tf.py` and
  `security/kubelinter.py` resolve the worktree they run in through `find_worktree_root`.
  `parse_kubelinter_json` is split into small helpers to stay within the complexity cap.
- [x] **No empty-state deploys from a worktree** (`commands/tf.py`, `tf/analysis.py`): the
  provider configurations keep local `terraform.tfstate` beside them, untracked, and
  `git worktree add` copies no untracked file, so a worktree's provider directory would plan to
  create every resource again. When the main checkout's directory holds local resource state
  and the worktree's does not, an auto-approved deploy stops, an interactive one asks first
  (default no), and a dry run only warns. A remote backend's cached configuration
  (`.terraform/terraform.tfstate`) is not resource state, so a remote backend never stops it.
- [x] **Automated Tests & Quality Gates**: each command is checked from a real nested
  worktree (`test_ai_repomap.py`, `test_ai_diagram.py`, `test_treesitter_engine.py`,
  `test_review_auto_fix.py`, `test_secops.py`, `test_tf.py`, `test_tf_analysis.py`), including
  the deploy guard's refusal, prompt, dry-run warning and remote-backend cases.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

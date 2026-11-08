# Tasks

## 1. Slug function and worktree title support

- [x] 1.1 Add `slug_from_title` to `src/devops_cli/git/branch_form.py` and test in `tests/git/test_branch_form.py`
  - Verification: `$ uv run devops ci test tests/git/test_branch_form.py`
- [x] 1.2 Support `--title` in `devops repos worktrees add` and test in `tests/core/test_repos_worktrees_add.py`
  - Verification: `$ uv run devops ci test tests/core/test_repos_worktrees_add.py`

## 2. Scaffold command and gate marker check

- [x] 2.1 Add scaffold marker refusal in `src/devops_cli/openspec/gate.py` and test in `tests/openspec/test_openspec_gate.py`
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_gate.py`
- [x] 2.2 Add `devops openspec new` command in `src/devops_cli/commands/openspec.py` and `src/devops_cli/openspec/scaffold.py`
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_new.py`

## 3. Project skills and documentation

- [x] 3.1 Add `devops-openspec-new` skill to `.claude/skills` and `.agents/skills`
  - Verification: `$ uv run devops openspec check`
- [x] 3.2 Regenerate documentation and CLI references
  - Verification: `$ uv run devops ci docs`

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

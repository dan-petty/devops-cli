# Task 487: SSH Key Prefix Reads devcontainer.json Holding URLs

**Issue**: [#487](https://github.com/dan-petty/devops-cli/issues/487)
**PR**: pending
**Status**: In Review
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

`_resolve_prefix_from_devcontainer` stripped JSONC comments with `re.sub(r"//.*$", ...)`, which
also cuts every string containing `//`. Since #485, `.devcontainer/devcontainer.json` holds
`"credential.https://github.com.helper"` values. The stripped text stopped parsing, the lookup
returned nothing, and `get_ssh_key_prefix()` fell back to the checkout directory's name. In a
checkout not named `devops-cli`, a git worktree for example, `devops ssh generate` named keys
after the directory, `test_ssh_generate_key_collision` failed, and the pre-push hook blocked
pushes. `commands/devcontainer.py` had already fixed the same bug with a string-aware stripper,
but this copy was missed.

### Key Deliverables Completed:

- [x] **One JSONC stripper**: `strip_json_comments` in `devops_cli.core.serialization`, used by
  the devcontainer command and the SSH key prefix lookup. The private copy in the command module
  is removed.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_ssh.py`: the devcontainer name is the prefix when a string holds `//` beside
    real comments.
  - `tests/test_devcontainer.py`: the existing JSONC tests target the shared function.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

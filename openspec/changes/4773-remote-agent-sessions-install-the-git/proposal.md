# Proposal: #4773

## Why

Claude Code cloud sessions (claude.ai/code) and the Copilot cloud agent install no git hooks, so their commits and pushes run no hook. Only the devcontainer runs `uv run pre-commit install`, at each start (`devops devcontainer post-start`). The end-of-file defect of `openspec/changes/archive/2026-11-02-3249-title-limit-round3/specs/roadmap-stage/spec.md` came from a plan commit of a cloud session. 16 commits since 2026-10-28 have a `Claude-Session` trailer. These sessions also skip the push gate `branch-current`. Closes #4773.

## What Changes

- `.claude/settings.json` and its template `src/devops_cli/templates/claude_settings.json.j2` get one SessionStart hook with the matcher `startup|resume`. The hook exits 0 when `CLAUDE_CODE_REMOTE` is not `true`, when `$CLAUDE_PROJECT_DIR/.pre-commit-config.yaml` does not exist or when `uv` is not on the PATH. Else it runs `uv run pre-commit install` in `$CLAUDE_PROJECT_DIR`, with its output on stderr, so it adds no text to the context of the session.
- `.github/workflows/copilot-setup-steps.yml` gets the step `uv run pre-commit install --install-hooks` after the tool install.
- `CONTRIBUTING.md` says how each agent host installs the hooks.
- The change carries a spec delta: the scaffolded settings and the hooks that a session installs are observable.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `devcontainer-agent-config`: Remote agent sessions install the git hooks.

## Impact

- Configuration: `.claude/settings.json`, `src/devops_cli/templates/claude_settings.json.j2`, `.github/workflows/copilot-setup-steps.yml`
- Documents: `CONTRIBUTING.md`
- Tests: `tests/commands/test_devcontainer.py`, `tests/invariants/test_workflow_contracts.py` (the contract test lists each command of the setup steps)
- A local session gets the hook too and exits 0 at once, because `CLAUDE_CODE_REMOTE` is not `true` there. A scaffolded repository (`devops devcontainer init`) gets the same hook.
- A cloud session start waits for `uv run`, which syncs the environment of the project on the first start. A failure of the hook does not block the session.

## Feasibility

- The Claude Code document "Configure cloud environments" (code.claude.com/docs/en/cloud-environments, read 2026-11-12) says: SessionStart hooks of the repository `.claude/settings.json` run in local and cloud sessions; the cloud VM sets `CLAUDE_CODE_REMOTE` to `true` and a local session never does; uv is installed; the default Limited allowlist holds `pypi.org`, `files.pythonhosted.org` and GitHub. Its own example hook uses the matcher `startup|resume` and `$CLAUDE_PROJECT_DIR`.
- The hooks reference (code.claude.com/docs/en/hooks) says that a SessionStart hook that fails does not block the session, that a `command` hook has a limit of 600 s, and that plain stdout of a SessionStart hook goes into the context.
- The GitHub documents of the Copilot cloud agent (read 2026-11-12) say that Copilot clones the repository after the setup steps only when the steps did not clone it, and that the firewall of the agent does not govern a process of a setup step. The workflow already checks out the repository.
- `.pre-commit-config.yaml` sets `default_install_hook_types: [pre-commit, pre-push]`. In a temporary clone, the hook command with `CLAUDE_CODE_REMOTE=true` wrote `.git/hooks/pre-commit` and `.git/hooks/pre-push` and exited 0 in 1.7 s with a warm uv cache. With the variable not set, set to `false`, with no `uv` on the PATH, or in a repository with no `.pre-commit-config.yaml`, it wrote no hook and exited 0. bash and dash gave the same result.
- No live cloud session or Copilot agent run is part of this check.

## Existing Tool Considered

Claude Code SessionStart hooks, the Copilot setup steps workflow and `pre-commit install` cover the need through their standard interfaces. The change adds configuration only and no code. Cost: about 50,000 tokens and 1 hour to build, near 0 to keep.

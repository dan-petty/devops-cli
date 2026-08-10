#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="$(pwd)"
UV_VERSION="0.12.3"

# ── uv ────────────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
  python3 -m pip install --user --upgrade "uv==${UV_VERSION}"
fi
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# ── Bash history persistence ────────────────────────────────────────────────
touch ~/.bash_history
chmod 600 ~/.bash_history

if ! grep -q 'HISTFILE=~/.bash_history' "${HOME}/.bashrc" 2>/dev/null; then
  cat >> "${HOME}/.bashrc" <<BASHRC

# ── Persistent bash history ──────────────────────────────────────────────────
export HISTFILE=~/.bash_history
export HISTSIZE=10000
export HISTFILESIZE=20000
shopt -s histappend
PROMPT_COMMAND="history -a\${PROMPT_COMMAND:+; \$PROMPT_COMMAND}"

# ── devops-cli venv ──────────────────────────────────────────────────────────
export PATH="${WORKSPACE_DIR}/.venv/bin:\$HOME/.local/bin:\$PATH"
BASHRC
fi

# ── devops-cli config ────────────────────────────────────────────────────────
if [[ -n "${DEVOPS_CLI_CONFIG:-}" && ! -f "${DEVOPS_CLI_CONFIG}" ]]; then
  echo ""
  echo "⚠  No project config found at: ${DEVOPS_CLI_CONFIG}"
  echo "   To create one, run:"
  echo "     cp config.example.yaml config.yaml"
  echo "   Then edit config.yaml with your settings."
fi

# ── Shell completions ─────────────────────────────────────────────────────────
if ! grep -q '_DEVOPS_COMPLETE' "${HOME}/.bashrc" 2>/dev/null; then
  cat >> "${HOME}/.bashrc" <<'BASHRC'

# ── devops-cli shell completion & alias ──────────────────────────────────────
if command -v devops &>/dev/null; then
  eval "$(_DEVOPS_COMPLETE=source_bash devops 2>/dev/null || true)"
  alias dot='devops'
fi
BASHRC
fi

echo ""
echo "✓ devops-cli devcontainer ready"
echo "  Run: devops --help"
echo "  Run: devops config init   (first-time setup)"
echo "  Run: devops install-tools (install kubectl, helm, argo, etc.)"

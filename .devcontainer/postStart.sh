#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="$(pwd)"
UV_VERSION="0.12.3"

# ── Git defaults ──────────────────────────────────────────────────────────────
git config --global push.autoSetupRemote true

# Prompt for git identity in interactive shells if not yet configured
if ! grep -q 'DEVOPS_GIT_IDENTITY_CHECK' "${HOME}/.bashrc" 2>/dev/null; then
  cat >> "${HOME}/.bashrc" <<'BASHRC'

# ── Git identity check ───────────────────────────────────────────────────────
# DEVOPS_GIT_IDENTITY_CHECK
if [[ $- == *i* ]] && [[ -t 0 ]] && [[ -t 1 ]] && \
   { [[ -z "$(git config --global user.name 2>/dev/null)" ]] || \
     [[ -z "$(git config --global user.email 2>/dev/null)" ]]; }; then
  _devops_valid_git_name='^[A-Za-z0-9 .,_-]{1,80}$'
  _devops_valid_git_email='^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
  echo ""
  echo "Git identity not configured."
  read -rp "  Name  : " _git_name
  read -rp "  Email : " _git_email

  if [[ -n "${_git_name}" ]]; then
    if [[ "${_git_name}" =~ ${_devops_valid_git_name} ]]; then
      git config --global user.name "${_git_name}"
    else
      echo "Name contains invalid characters; skipped."
    fi
  fi

  if [[ -n "${_git_email}" ]]; then
    if [[ "${_git_email}" =~ ${_devops_valid_git_email} ]]; then
      git config --global user.email "${_git_email}"
    else
      echo "Email format is invalid; skipped."
    fi
  fi

  [[ -n "${_git_name}" && -n "${_git_email}" ]] && echo "Git identity saved."
  unset _git_name _git_email _devops_valid_git_name _devops_valid_git_email
  echo ""
fi
BASHRC
fi

# ── uv ────────────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
  python3 -m pip install --user --upgrade "uv==${UV_VERSION}"
fi
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# ── Python 3.14.6 (pinned via .python-version) ───────────────────────────────
uv python install "$(cat "${WORKSPACE_DIR}/.python-version" | tr -d '[:space:]')"

# ── Project dependencies ──────────────────────────────────────────────────────
uv sync

# ── SSH key permissions ───────────────────────────────────────────────────────
if [ -d "${HOME}/.ssh" ]; then
  # Recursive chown only when needed — avoids an unconditional sudo call on every start.
  if [ "$(stat -c '%U' "${HOME}/.ssh")" != "vscode" ]; then
    sudo chown -R vscode:vscode "${HOME}/.ssh"
  fi
  chmod 700 "${HOME}/.ssh"
  find "${HOME}/.ssh" -maxdepth 1 -name "id_*" ! -name "*.pub" -exec chmod 600 {} +
  find "${HOME}/.ssh" -maxdepth 1 -name "*.pub" -exec chmod 644 {} +
fi

# ── Kubernetes kubeconfig ─────────────────────────────────────────────────────
KUBECONFIG_DIR="${HOME}/.kube"
KUBECONFIG_FILE="${KUBECONFIG_DIR}/config"
mkdir -p "${KUBECONFIG_DIR}"
if [ ! -f "${KUBECONFIG_FILE}" ]; then
  cat > "${KUBECONFIG_FILE}" <<'KUBECONFIG'
apiVersion: v1
kind: Config
clusters: []
contexts: []
current-context: ""
preferences: {}
users: []
KUBECONFIG
  chmod 600 "${KUBECONFIG_FILE}"
fi

# ── Minikube autostart ────────────────────────────────────────────────────────
if [ "${DEVOPS_MINIKUBE_AUTOSTART:-true}" = "true" ]; then
  if command -v minikube &>/dev/null; then
    if ! minikube status --format='{{.Host}}' 2>/dev/null | grep -q "Running"; then
      echo "Starting minikube (docker driver)..."
      minikube start \
        --driver=docker \
        --cpus=2 \
        --memory=4096 \
        --wait=all \
        --embed-certs=true \
        2>&1 | tail -3
      minikube addons enable metrics-server 2>/dev/null || true
      echo "✓ minikube running"
    else
      echo "✓ minikube already running"
    fi
  fi
fi

# ── Git SSH commit signing ────────────────────────────────────────────────────
NEWEST_KEY=$(find "${HOME}/.ssh" -maxdepth 1 -type f \
  \( -name "id_ed25519*" -o -name "id_ecdsa*" -o -name "id_rsa*" \) \
  ! -name "*.pub" | sort | tail -1 || true)
if [ -n "${NEWEST_KEY:-}" ]; then
  git config --global gpg.format ssh
  git config --global user.signingkey "${NEWEST_KEY}"
  git config --global commit.gpgsign true
  git config --global tag.gpgsign true
  echo "git signing configured: ${NEWEST_KEY##*/}"
fi

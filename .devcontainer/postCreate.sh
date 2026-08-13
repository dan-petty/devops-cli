#!/usr/bin/env bash
# Legacy wrapper delegating to native devops CLI lifecycle engine
set -euo pipefail

if command -v devops &>/dev/null; then
  devops devcontainer run-lifecycle --post-create
elif command -v uv &>/dev/null; then
  uv run devops devcontainer run-lifecycle --post-create
else
  python3 -m devops_cli.main devcontainer run-lifecycle --post-create
fi

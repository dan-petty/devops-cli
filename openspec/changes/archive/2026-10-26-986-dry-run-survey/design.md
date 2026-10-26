# Design

## Survey Methodology

The survey enumerates all commands that declare `--dry-run` by traversing the Click and Typer command tree.
Each command path is classified by its argument requirements:
- Commands with required arguments or options.
- Commands that run without arguments (zero arguments or optional arguments).

Every command executes with `typer.testing.CliRunner` in an isolated environment.
A monkeypatched `subprocess.run` records every child process command line without executing the real process.
The network guard blocks external socket communication.
Each recorded process execution is classified into one of three categories:
- `local read`: inspects local file or repository state (e.g., `git remote get-url origin`, `git rev-parse`).
- `local write`: modifies local file state or directory contents.
- `external`: transmits requests to remote servers or APIs (e.g., `kubectl apply`, `gh api`).

A command is an offender if `--dry-run` executes a `local write` or an `external` call.

## Baseline Reconciliation

Issue #885 surveyed 80 argument-free command paths at commit `9c879ae` (tip of `release/v0.2.25`).
At commit `9c879ae`:
- 120 total commands declared `--dry-run`.
- 80 commands ran without required arguments (47 zero-argument commands, 33 optional-argument commands).
- 40 commands required arguments.

At current commit `a155b0ca` (`v0.6.4`):
- 225 total commands declare `--dry-run`.
- 174 commands run without required arguments (114 zero-argument commands, 60 optional-argument commands).
- 51 commands require positional arguments or required options.

The sum is exact: $174 + 51 = 225$ total commands.
Between `v0.2.25` and `v0.6.4`, 105 new commands declaring `--dry-run` were added to the CLI:
- 11 new commands with required arguments (expanding from 40 to 51).
- 94 new commands without required arguments (expanding from 80 to 174).

## Survey Results: 51 Argument-Taking Commands

The table below lists all 51 argument-taking command paths that declare `--dry-run` at surveyed commit `a155b0ca`.
Every cell contains recorded survey data.

| Command | Placeholder Arguments | Exit Code | Recorded Processes | Process Classification | Remote / File Writes | Finding |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `devops ai analyze pr` | `1` | 1 | `git remote get-url origin`<br>`gh api rate_limit` | local read, external | external API call | **Yes** |
| `devops ai ast parse` | `/tmp/tmpme2v5zsx/example.txt` | 0 | none | none | none | No |
| `devops ai harness run` | `echo test` | 0 | none | none | none | No |
| `devops ai pack-context` | `/tmp/tmpme2v5zsx` | 0 | none | none | none | No |
| `devops ai rag query` | `example-query` | 0 | none | none | none | No |
| `devops ai rag search` | `example-query` | 0 | none | none | none | No |
| `devops ai read` | `/tmp/tmpme2v5zsx/example.txt` | 0 | none | none | none | No |
| `devops ai research annotate` | `/tmp/tmpme2v5zsx/example.txt` | 0 | none | none | none | No |
| `devops ai research forage` | `example-anchor` | 0 | none | none | none | No |
| `devops ai research model` | `example-topic` | 0 | none | none | none | No |
| `devops ai review pr` | `1` | 1 | none | none | none | No |
| `devops ai test-gen` | `/tmp/tmpme2v5zsx/example.txt` | 0 | none | none | none | No |
| `devops argo cd fleet sync` | `example-app` | 0 | none | none | none | No |
| `devops argo fleet sync` | `example-app` | 0 | none | none | none | No |
| `devops argo rollouts abort` | `example-rollout` | 0 | none | none | none | No |
| `devops argo rollouts analyze` | `example-rollout` | 1 | none | none | none | No |
| `devops argo rollouts promote` | `example-rollout` | 0 | none | none | none | No |
| `devops argo rollouts restart` | `example-rollout` | 0 | none | none | none | No |
| `devops cloudflare dns delete` | `example.com` | 1 | none | none | none | No |
| `devops config unset` | `example-key` | 0 | none | none | none | No |
| `devops docker analyze-layers` | `example-image:latest` | 0 | none | none | none | No |
| `devops docker push` | `example-image:latest` | 0 | none | none | none | No |
| `devops docker sandbox` | `echo test` | -1 | none | none | none | No |
| `devops docker sign` | `example-image:latest` | 0 | none | none | none | No |
| `devops docker verify` | `example-image:latest` | 0 | none | none | none | No |
| `devops gh secrets sync` | `--secret-names SECRET_1` | 0 | none | none | none | No |
| `devops grafana dashboards import` | `/tmp/tmpme2v5zsx/example.json` | 1 | none | none | none | No |
| `devops k8s apply` | `/tmp/tmpme2v5zsx/example.yaml` | 0 | `kubectl apply -f /tmp/tmpme2v5zsx/example.yaml --dry-run=client` | external | external API call | **Yes** |
| `devops k8s create-tls-secret` | `example-secret` | 0 | none | none | none | No |
| `devops k8s diff-helm` | `example-release` | 0 | none | none | none | No |
| `devops k8s run-job` | `echo test` | 0 | none | none | none | No |
| `devops k8s stream-logs` | `example-pod` | 0 | none | none | none | No |
| `devops k8s switch-context` | `example-context` | 0 | none | none | none | No |
| `devops k8s volume move` | `default/example-pvc` | 0 | none | none | none | No |
| `devops k8s volume reclaim` | `example-pv` | 0 | none | none | none | No |
| `devops openspec archive` | `example-change` | 0 | none | none | none | No |
| `devops prometheus analyze` | `up` | 0 | none | none | none | No |
| `devops prometheus query` | `up` | 0 | none | none | none | No |
| `devops repos clone` | `https://example.com/repo.git` | 0 | none | none | none | No |
| `devops review pr` | `1` | 1 | none | none | none | No |
| `devops roadmap return` | `1 --comment evidence --repo dan-petty/devops-cli` | 0 | none | none | none | No |
| `devops sandbox metrics` | `example-id` | 0 | none | none | none | No |
| `devops sandbox probe` | `example-id` | 0 | none | none | none | No |
| `devops telemetry semconv refresh` | `--commit HEAD` | 0 | none | none | none | No |
| `devops test sandbox` | `echo test` | -1 | none | none | none | No |
| `devops tf deploy-cloud` | `--provider aws` | 0 | none | none | none | No |
| `devops valkey set` | `example-key example-val` | 0 | none | none | none | No |
| `devops vault get` | `secret/example` | 0 | none | none | none | No |
| `devops vault leases` | `--revoke example-lease` | 0 | none | none | none | No |
| `devops vault set` | `secret/example k=v` | 0 | none | none | none | No |
| `devops vault sync` | `secret/example` | 0 | none | none | none | No |

## Candidates Filed

The survey identified two offenders among the 51 argument-taking commands outside `commands/ci.py`.
Each offender was filed as a candidate via `devops roadmap intake ... --confirm`:

1. **#2312**: `fix(k8s): devops k8s apply runs for real under its own --dry-run`
   - Offense: `devops k8s apply <path>` omits `set_dry_run(dry_run)`, causing `is_dry_run()` to evaluate to `False`. The command runs `kubectl apply -f <path> --dry-run=client` against the live cluster.
2. **#2314**: `fix(ai): devops ai analyze pr runs for real under its own --dry-run`
   - Offense: `devops ai analyze pr <number>` calls `get_pull` and `get_pull_files` (triggering `gh pr view` and rate limit checks) against the GitHub API before evaluating dry-run state.

## Survey and Recording Script

The following script extracted the Click tree, injected placeholder arguments, and recorded subprocess executions:

```python
import importlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
import typer
from typer.testing import CliRunner

from devops_cli.config.constants import CONST_CLI_ROOT_LEVEL_COMMANDS
from devops_cli.dry_run import set_dry_run
from devops_cli.main import _COMMAND_SPECS

runner = CliRunner()
recorded_calls = []


def fake_subprocess_run(cmd, *args, **kwargs):
    cmd_list = list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)]
    recorded_calls.append(cmd_list)
    if cmd_list[:3] == ["gh", "auth", "token"]:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ghp_fake\n", stderr="")
    if cmd_list[:3] == ["git", "remote", "get-url"]:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="https://github.com/dan-petty/devops-cli.git\n",
            stderr="",
        )
    if cmd_list[:2] == ["git", "describe"]:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="v0.6.4\n", stderr="")
    if cmd_list[:2] == ["git", "rev-parse"]:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="dummy_sha\n", stderr="")
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="{}", stderr="")


def classify_argv(argv):
    prog = argv[0] if argv else ""
    if prog == "git":
        sub = argv[1] if len(argv) > 1 else ""
        if sub in ("status", "rev-parse", "describe", "diff", "log", "branch", "show", "remote"):
            return "local read"
        return "local write"
    if prog in ("kubectl", "helm", "gh", "argocd", "tofu", "terraform", "curl"):
        return "external"
    return "local read"
```

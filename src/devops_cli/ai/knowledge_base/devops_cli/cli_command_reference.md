# DevOps CLI Command Surface Reference

This document provides a comprehensive operational reference for all CLI command groups, subcommands, and flags implemented in `devops-cli`.

---

## Command Groups Overview

| Group | Subcommand | Purpose | Primary Flags / Arguments |
| :--- | :--- | :--- | :--- |
| **`ai`** | `review branch` | AI multi-persona branch code review | `--target`, `--persona`, `--all-personas`, `--summary` |
| | `review path` | AI multi-persona path/file code review | `path`, `--persona`, `--all-personas`, `--summary` |
| | `review pr` | Review GitHub pull request by number | `number`, `--repo`, `--post-comment` |
| | `review findings` | Inspect review findings for a session | `--session`, `--status`, `--unverified`, `--verified` |
| | `review verify` | Validate/invalidate review findings | `--session`, `--index`, `--title`, `--status`, `--reason` |
| | `review stats` | Display review accuracy statistics | `--reviews-dir` |
| | `chat` | Interactive multi-turn AI terminal assistant | `prompt`, `--provider`, `--model`, `--system` |
| | `rag index` | Index workspace code & docs into Qdrant | `target`, `--force`, `--include-kb` |
| | `rag query` | Semantic search over indexed embeddings | `query`, `--collection`, `--limit` |
| | `cache status` | LLM response cache hit rates & stats | `--format` |
| | `cache clear` | Purge in-memory and disk LLM cache | |
| **`k8s`** | `bootstrap` | Bootstrap Minikube & deploy stack | `--dir`, `--auto-start`, `--stack` |
| | `deploy-stack` | Deploy infra, llm, or all stacks | `--stack`, `--dir`, `--context` |
| | `teardown-stack`| Clean teardown of stack components | `--stack`, `--dir`, `--context` |
| | `contexts` | List kubeconfig contexts | |
| | `switch-context`| Switch active kubeconfig context | `name` |
| | `status` | Cluster node and pod status | |
| | `apply` | Apply Kubernetes manifest via kubectl | `path`, `--namespace`, `--dry-run` |
| | `logs` | Stream pod container logs | `pod`, `--container`, `--namespace`, `--follow` |
| | `lint` | Manifest security audit with KubeLinter | `target`, `--dry-run` |
| | `audit` | Cluster health sanitization with Popeye | `--dry-run` |
| | `check-deprecated`| Scan for deprecated APIs with Pluto | `target`, `--dry-run` |
| **`scan`** | `scan` | Vulnerability & secret scanning with Trivy | `target`, `--type`, `--severity`, `--json` |
| **`repos`** | `clone-org` | Clone all repositories in GitHub org | `org`, `--dest`, `--concurrency` |
| | `sync` | Sync repos & generate `.code-workspace`| `--root`, `--prune` |
| | `list` | List managed repositories | `--root` |
| **`ssh`** | `generate` | Generate Ed25519 or RSA SSH key pair | `name`, `--type`, `--bits`, `--comment` |
| | `register` | Register SSH key on GitHub for auth & signing | `--key-file`, `--title` |
| | `rotate` | Rotate expired or aging SSH keys | `--key-dir`, `--force` |
| | `audit` | Audit SSH key permissions & security | `--key-dir` |
| **`tls`** | `ca` | Generate Root Certificate Authority (CA)| `--output-dir`, `--cn`, `--org`, `--days` |
| | `cert` | Generate server certificate signed by CA| `domain`, `--output-dir`, `--days` |
| | `homelab` | Generate complete Homelab TLS bundle | `--output-dir`, `--domains`, `--ips` |
| | `enable-k8s` | Deploy TLS secrets to K8s namespaces | `--context`, `--secret-name`, `--stack` |
| **`telemetry`**| `status` | Check OpenTelemetry & Jaeger status | |
| | `test` | Send test trace spans | `--spans` |
| **`docs`** | `generate` | Regenerate CLI docs & sync README | `--sync-readme`, `--check` |
| **`config`** | `show` | Display active configuration table | |
| | `get` | Get specific dotted config setting | `key` |
| | `set` | Set dotted config value (or Keyring) | `key`, `value` |
| **`ci`** | `ci` | Execute 10-point local quality gate | `--quick`, `--skip-tests` |
| **`release`** | `release` | Bump version & cut release branch | `bump_type`, `--push`, `--dry-run` |
| **`serve`** | `serve` | Start FastAPI REST & OpenAPI daemon | `--host`, `--port`, `--reload` |
| **`devcontainer`**| `scaffold` | Scaffold `.devcontainer` configuration | `--dest`, `--template` |

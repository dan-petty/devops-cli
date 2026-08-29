# DevOps CLI Command Surface Reference

This document provides a comprehensive operational reference for all CLI command groups, subcommands, and flags implemented in `devops-cli`.

---

## Command Groups Overview

| Group | Subcommand | Purpose | Primary Flags / Arguments |
| :--- | :--- | :--- | :--- |
| **`ai`** | `review branch` | AI multi-persona branch code review | `--target`, `--persona`, `--all`, `--summary`, `--no-<stage>`, `--<stage>-only` |
| | `review path` | AI multi-persona path/file code review | `path`, `--persona`, `--all`, `--summary`, `--no-<stage>`, `--<stage>-only` |
| | `review pr` | Review GitHub pull request by number | `number`, `--repo`, `--post`, `--no-<stage>`, `--<stage>-only` |
| | `review findings` | Inspect review findings for a session | `--session`, `--status`, `--unverified`, `--verified`, `--invalidated`, `--details` |
| | `review verify` | Validate/invalidate review findings with reasons | `--session`, `--index`, `--title`, `--status`, `--reason` |
| | `review patch` | Interactive preview and patch application | `--session`, `--index`, `--apply`, `--dry-run` |
| | `review export-feedback`| Export findings to fine-tuning/RAG dataset | `--session`, `--status`, `--output` |
| | `review stats` | Display review accuracy statistics | `--reviews-dir` |
| | `chat` | Interactive multi-turn AI terminal assistant | `prompt`, `--provider`, `--model`, `--system` |
| | `repomap` | Generate structural AI repository map | `--output`, `--max-depth`, `--exclude` |
| | `diagram` | Generate Mermaid architecture diagrams | `target`, `--output`, `--theme` |
| | `test-gen` | Scaffold isolated unit test cases | `target_file`, `--output`, `--framework` |
| | `rag index` | Index workspace code & docs into Qdrant | `target`, `--force`, `--include-kb` |
| | `rag query` | Semantic search over indexed embeddings | `query`, `--collection`, `--limit` |
| | `cache status` | LLM response cache hit rates & stats | `--format` |
| | `cache clear` | Purge in-memory and disk LLM cache | |
| **`k8s`** | `bootstrap` | Bootstrap Minikube & deploy stack | `--dir`, `--auto-start`, `--stack` |
| | `deploy-stack` | Deploy infra, otel, llm, or all stacks | `--stack`, `--dir`, `--context` |
| | `teardown-stack`| Clean teardown of stack components | `--stack`, `--dir`, `--context` |
| | `contexts` | List kubeconfig contexts | |
| | `switch-context`| Switch active kubeconfig context | `name` |
| | `status` | Cluster node and pod status | |
| | `pods` | Real-time pod listing and status | `--namespace`, `--all-namespaces` |
| | `apply` | Apply Kubernetes manifest via kubectl | `path`, `--namespace`, `--dry-run` |
| | `logs` | Stream pod container logs | `pod`, `--container`, `--namespace`, `--follow` |
| | `lint` | Manifest security audit with KubeLinter | `target`, `--dry-run` |
| | `audit` | Cluster health sanitization with Popeye | `--dry-run` |
| | `check-deprecated`| Scan for deprecated APIs with Pluto | `target`, `--dry-run` |
| | `enable-tls` | Deploy TLS certificates to namespace | `--context`, `--secret-name`, `--stack` |
| **`kustomize`**| `build` | Render hydrated Kubernetes manifests | `path`, `--output` |
| | `diff` | Diff hydrated manifests against cluster | `path`, `--context` |
| **`tf`** | `init` | Initialize OpenTofu/Terraform working directory | `dir`, `--upgrade` |
| | `plan` | Generate speculative execution plan | `dir`, `--out`, `--var-file` |
| | `apply` | Apply infrastructure configuration | `dir`, `--auto-approve` |
| | `output` | Read structured state outputs | `dir`, `--json` |
| | `destroy` | Destroy managed cloud resources | `dir`, `--auto-approve` |
| | `notify-plan` | Post plan output to GitHub PR or Slack | `dir`, `--target` |
| **`scan`** | `scan` | Vulnerability & secret scanning with Trivy | `target`, `--type`, `--severity`, `--json` |
| **`uv`** | `audit` | Scan Python virtualenv for CVEs via pip-audit | `--strict`, `--fix` |
| **`repos`** | `clone-org` | Clone all repositories in GitHub org | `org`, `--dest`, `--concurrency` |
| | `sync` | Sync repos & generate `.code-workspace`| `--root`, `--prune` |
| | `list` | List managed repositories and status | `--root` |
| **`workspace`**| `init` | Initialize multi-org workstation workspace | `--root` |
| | `sync` | Synchronize multi-repo `.code-workspace` | `--root` |
| **`branches`** | `list` | List active local and remote branches | `--remote`, `--merged` |
| | `tidy` | Prune stale local branches merged into main | `--force` |
| **`pr`** | `list` | List open GitHub pull requests | `--repo`, `--author` |
| | `view` | View pull request diff and metadata | `number`, `--repo` |
| | `checkout` | Checkout pull request branch locally | `number`, `--repo` |
| | `create` | Open GitHub pull request | `--title`, `--body`, `--base` |
| **`docker`** | `ps` | List running Docker containers | `--all` |
| | `stats` | Real-time container CPU/memory telemetry | |
| | `clean` | Prune unused images, containers, volumes | `--force` |
| **`argo`** | `apps` | List ArgoCD applications and sync health | `--server`, `--auth-token` |
| | `sync` | Synchronize declarative ArgoCD application | `app_name` |
| **`grafana`** | `dashboards` | List deployed Grafana dashboards | `--server`, `--api-key` |
| | `export` | Export dashboard JSON manifests | `uid`, `--out` |
| **`prometheus`**| `query` | Execute PromQL instant query | `query`, `--server` |
| | `alerts` | Check active Prometheus alert firing state | `--server` |
| **`ssh`** | `generate` | Generate Ed25519 or RSA SSH key pair | `name`, `--type`, `--bits`, `--comment` |
| | `register` | Register SSH key on GitHub for auth & signing | `--key-file`, `--title` |
| | `rotate` | Rotate expired or aging SSH keys | `--key-dir`, `--force` |
| | `audit` | Audit SSH key permissions & security | `--key-dir` |
| **`tls`** | `ca` | Generate Root Certificate Authority (CA)| `--output-dir`, `--cn`, `--org`, `--days` |
| | `cert` | Generate server certificate signed by CA| `domain`, `--output-dir`, `--days` |
| | `homelab` | Generate complete Homelab TLS bundle | `--output-dir`, `--domains`, `--ips` |
| | `inspect` | Inspect X.509 certificate expiry & SANs | `cert_file` |
| **`telemetry`**| `status` | Check OpenTelemetry & Jaeger status | |
| | `test` | Send test trace spans | `--spans` |
| | `profile` | Profile subcommand execution latency & CPU | `command` |
| **`docs`** | `generate` | Regenerate CLI docs & sync README | `--sync-readme`, `--check` |
| **`config`** | `show` | Display active configuration table | |
| | `get` | Get specific dotted config setting | `key` |
| | `set` | Set dotted config value (or Keyring) | `key`, `value` |
| | `audit-keys` | Audit config for unencrypted plaintext keys | |
| | `output` | Output raw YAML or JSON configuration | `--json` |
| **`ci`** | `ci` | Execute 10-point local quality gate | `--quick`, `--skip-tests` |
| **`release`** | `release` | Bump version & cut release branch | `bump_type`, `--push`, `--dry-run` |
| **`serve`** | `serve` | Start FastAPI REST & OpenAPI daemon | `--host`, `--port`, `--reload` |
| **`devcontainer`**| `scaffold` | Scaffold `.devcontainer` configuration | `--dest`, `--template` |

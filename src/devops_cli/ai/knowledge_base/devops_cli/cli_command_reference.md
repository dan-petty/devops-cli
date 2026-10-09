# DevOps CLI Command Surface Reference

This document provides an overview of the main command groups implemented in `devops-cli`. The complete generated reference is docs/CLI_REFERENCE.md (`devops docs generate`).

---

## Command Groups Overview

| Group | Subcommand | Purpose | Primary Flags / Arguments |
| :--- | :--- | :--- | :--- |
| **`ai`** | `devops ai review branch` | AI multi-persona branch code review | `branch_name`, `--base`, `--repo`, `--persona`, `--all`, `--summary`, `--no-<stage>`, `--<stage>-only` |
| | `devops ai review path` | AI multi-persona path/file code review | `path`, `--persona`, `--all`, `--summary`, `--no-<stage>`, `--<stage>-only` |
| | `devops ai review pr` | Review GitHub pull request by number | `number`, `--repo`, `--post`, `--no-<stage>`, `--<stage>-only` |
| | `devops ai review findings` | Inspect a session's findings, or with `--candidates` every finding it raised | `--session`, `--status`, `--severity`, `--unverified`, `--verified`, `--invalidated`, `--mitigated`, `--candidates`, `--details` |
| | `devops ai review verify` | Record a person's verdict on a finding or candidate | `--session`, `--index`, `--title`, `--candidate`, `--status` (required), `--reason` |
| | `devops ai review benchmark` | Review the same files several times and report median time/tokens per stage | `targets`, `--runs`, `--pattern`, `--persona`, `--all` |
| | `devops ai review export-feedback` | Export findings to a JSONL feedback dataset | `--output`, `--reviews-dir`, `--status` |
| | `devops ai review stats` | Display review accuracy statistics | `--reviews-dir` |
| | `devops ai chat` | Interactive chat with a Pydantic AI persona | `--persona`, `--model`, `--context`, `--rag`, `--tools`, `--thinking` |
| | `devops ai repomap` | Generate structural AI repository map | `--target`, `--max-files`, `--include-tests`, `--multilingual`, `--json` |
| | `devops ai diagram` | Generate Mermaid architecture diagrams | `diagram_type` (arch\|threat), `--target`, `--json` |
| | `devops ai test-gen` | Scaffold isolated unit test cases | `target_file`, `--function`, `--json` |
| | `devops ai rag index` | Index workspace code & docs into Qdrant | `target`, `--force`, `--include-kb` |
| | `devops ai rag query` | Semantic search over indexed embeddings | `query`, `--collection`, `--top-k`, `--min-score` |
| | `devops ai cache status` | LLM response cache hit rates & stats | `--format` |
| | `devops ai cache clear` | Purge in-memory and disk LLM cache | |
| **`k8s`** | `devops k8s bootstrap` | Bootstrap Minikube & deploy stack | `--dir`, `--auto-start`, `--stack` |
| | `devops k8s deploy-stack` | Deploy infra, llm, logging, or all stacks | `--stack`, `--k8s-dir`, `--context`, `--wait`, `--timeout` |
| | `devops k8s teardown-stack` | Clean teardown of stack components | `--stack`, `--k8s-dir`, `--context` |
| | `devops k8s contexts` | List kubeconfig contexts | |
| | `devops k8s switch-context` | Switch active kubeconfig context | `name` |
| | `devops k8s status` | Cluster node and pod status | |
| | `devops k8s pods` | Real-time pod listing and status | `--namespace`, `--all-namespaces` |
| | `devops k8s apply` | Apply Kubernetes manifest via kubectl | `path`, `--namespace`, `--dry-run` |
| | `devops k8s logs` | Stream pod container logs | `pod`, `--container`, `--namespace`, `--follow` |
| | `devops k8s lint` | Manifest security audit with KubeLinter | `target`, `--dry-run` |
| | `devops k8s audit` | Cluster health sanitization with Popeye | `--dry-run` |
| | `devops k8s check-deprecated` | Scan for deprecated APIs with Pluto | `target`, `--dry-run` |
| | `devops k8s enable-tls` | Deploy TLS certificates to namespace | `--context`, `--secret-name`, `--stack` |
| **`kustomize`** | `devops kustomize build` | Render hydrated Kubernetes manifests | `path`, `--output` |
| | `devops kustomize diff` | Diff hydrated manifests against cluster (kubectl diff -k) | `path` |
| **`tf`** | `devops tf init` | Initialize OpenTofu/Terraform working directory | `dir`, `--upgrade` |
| | `devops tf plan` | Generate speculative execution plan | `dir`, `--out`, `--var-file` |
| | `devops tf apply` | Apply infrastructure configuration | `dir`, `--auto-approve` |
| | `devops tf output` | Read structured state outputs | `dir`, `--json` |
| | `devops tf destroy` | Destroy managed cloud resources | `dir`, `--auto-approve` |
| | `devops tf notify-plan` | Post plan output as a GitHub PR comment | `--plan-file`, `--pr`, `--dry-run`, `--json` |
| **`scan`** | `devops scan trivy` | Vulnerability & misconfiguration scanning with Trivy | `target`, `--type`, `--severity`, `--json` |
| | `devops scan secrets` | Secret scanning with Gitleaks | `target`, `--json` |
| | `devops scan sast` | Static analysis with Semgrep | `target`, `--json` |
| | `devops scan iac` | Infrastructure-as-code scanning | `target`, `--json` |
| | `devops scan report` | Comprehensive multi-tool security report | `target`, `--json` |
| **`uv`** | `devops uv sync` | Sync project dependencies | `--frozen` |
| **`repos`** | `devops repos clone-org` | Clone all repositories in GitHub org | `org`, `--base-dir`, `--private`, `--forks` |
| | `devops repos sync` | Fetch (and optionally pull) tracking branches across repos | `--base-dir`, `--pull`, `--dry-run` |
| | `devops repos list` | List managed repositories and status | `--base-dir` |
| **`workspace`** | `devops workspace generate` | Regenerate the .code-workspace from all repos | `--base-dir`, `--workspace` |
| | `devops workspace add` | Add a folder to the multi-repo workspace | `repo_path`, `--workspace` |
| | `devops workspace remove` | Remove a folder from the multi-repo workspace | `repo_path`, `--workspace` |
| **`branches`** | `devops branches list` | List active local and remote branches | `--base-dir`, `--all` |
| | `devops branches clean` | Delete local branches merged into main/master | `--base-dir`, `--dry-run` |
| **`pr`** | `devops pr list` | List open GitHub pull requests | `--state`, `--limit`, `--repo` |
| | `devops pr view` | View pull request diff and metadata | `number`, `--repo` |
| | `devops pr check-readiness` | Validate PR merge readiness | `number`, `--repo` |
| | `devops pr create` | Open GitHub pull request | `--title`, `--body`, `--base` |
| **`docker`** | `devops docker images` | List local Docker images | `--name` |
| | `devops docker stats` | Real-time container CPU/memory telemetry | |
| | `devops docker prune` | Remove unused containers, images, networks | `--volumes`, `--force` |
| **`argo`** | `devops argo cd apps list` | List ArgoCD applications | |
| | `devops argo sync` | Synchronize declarative ArgoCD application | `app_name` |
| **`grafana`** | `devops grafana dashboards list` | List Grafana dashboards | |
| | `devops grafana dashboards export` | Export a dashboard to JSON | `uid`, `--output` |
| **`prometheus`** | `devops prometheus query` | Execute PromQL instant query | `expr`, `--time` |
| | `devops prometheus rules` | List recording and alerting rules | |
| **`ssh`** | `devops ssh generate` | Generate an SSH key pair | `--key-dir`, `--prefix`, `--comment` |
| | `devops ssh register` | Register SSH key on GitHub for auth & signing | `--key-file`, `--title` |
| | `devops ssh rotate` | Rotate expired or aging SSH keys | `--key-dir`, `--force` |
| | `devops ssh audit` | Audit SSH key permissions & security | `--key-dir` |
| **`tls`** | `devops tls ca` | Generate Root Certificate Authority (CA) | `--output-dir`, `--common-name`, `--organization`, `--validity-days` |
| | `devops tls cert` | Generate server certificate signed by CA | `--common-name`, `--san`, `--ca-cert`, `--ca-key`, `--validity-days` |
| | `devops tls homelab` | Generate complete Homelab TLS bundle | `--output-dir`, `--domain`, `--ip` |
| | `devops tls inspect` | Inspect X.509 certificate expiry & SANs | `cert_file` |
| **`telemetry`** | `devops telemetry status` | Check OpenTelemetry & Jaeger status | |
| | `devops telemetry test` | Emit a test span and metric to the collector | `--name`, `--logfire` |
| | `devops telemetry profile` | Profile subcommand execution latency & CPU | `command` |
| **`docs`** | `devops docs generate` | Regenerate CLI docs & sync README | `--sync-readme`, `--check` |
| | `devops docs check` | Validate documentation matches CLI surface | |
| **`config`** | `devops config show` | Display active configuration table | |
| | `devops config get` | Get specific dotted config setting | `key` |
| | `devops config set` | Set dotted config value (or Keyring) | `key`, `value` |
| | `devops config audit-keys` | Audit config for unencrypted plaintext keys | |
| | `devops config output` | List configuration environment variables | `--export`, `--json` |
| **`ci`** | `devops ci` | Run every check of the local quality gate | `--fix/--no-fix`, `--check`, `--cache`, `--force`, `--files` |
| | `devops ci run` | Same as `devops ci` | `--fix` |
| | `devops ci audit` | Check dependencies for known CVEs (uv audit) | |
| | `devops ci mutate` | Mutation-test changed functions with mutmut and show the survivors; never a gate | `paths`, `--changed`, `--base` |
| **`release`** | `devops release prepare` | Bump version, update changelog, sync docs | `version`, `--create-pr`, `--type` |
| | `devops release pr` | Create release branch and release PR | `--version`, `--base`, `--push` |
| | `devops release check` | Verify release readiness | |
| **`serve`** | `devops serve` | Start FastAPI REST & OpenAPI daemon | `--host`, `--port`, `--reload` |
| **`devcontainer`** | `devops devcontainer init` | Scaffold `.devcontainer` configuration | `path`, `--force` |
| | `devops devcontainer validate` | Validate devcontainer configuration | `path` |

# Security Policy — DevOps CLI

DevOps CLI follows an enterprise zero-trust security model designed to safeguard developer workstations, local and remote Kubernetes clusters, CI/CD pipelines, and agentic AI execution environments.

---

## Supported Versions

Only the latest release gets security fixes. A fix ships in the next release.

---

## Zero-Trust Security & Egress Safety Principles

All code authored in or evaluated by DevOps CLI must strictly adhere to the following security guarantees:

1. **Zero Secret Leakage**: Plaintext secrets, tokens, private keys, or API credentials must never be committed to code repositories, written to unencrypted configuration files, or emitted into terminal outputs/logs. Each secret comes from a secret store: the OS keyring, HashiCorp Vault, a Kubernetes Secret or the credential store of the tool that owns it. Never copy the content of a gitignored file (`.env*`, `.ssh/`, `.data/`, credentials, private keys) into a document, changelog, finding, commit or code.
2. **Strict Egress & SSRF Protection**: All outbound network requests originating from AI models, documentation crawlers, or Kubernetes API clients must validate destination endpoints against private/loopback IP address ranges to prevent Server-Side Request Forgery (SSRF). A connector to a configured internal service (Valkey, Vault, the `k8s://` proxy and cluster-service clients, Prometheus, Loki, Ollama, the LLM gateway) reaches a private network by design. The `k8s://` proxy and cluster-service clients are checked at the connect. The in-process `kubernetes` client (urllib3) is not: it is trusted because its address comes from the operator's kubeconfig or the in-cluster environment. SSRF applies to an untrusted URL that a client dials outside the factory `devops_cli.http.client`.
3. **Subprocess Bounded Execution**: All external commands (`git`, `helm`, `kubectl`, `tofu`, `docker`) are executed via bounded argument lists (preventing shell injection) with mandatory non-infinite timeouts.
4. **Data Isolation**: Agent-generated review logs, benchmarks, and temporary telemetry artifacts are isolated under dedicated agent subfolders (`<data_dir>/agent`, e.g. `./.data/agent`), completely segregated from the primary user workspace data tier (`DEVOPS_CLI_DATA_DIR` / `data.dir`).
5. **Least Privilege Runtime**: Kubernetes pods, Docker containers, and CI jobs run under unprivileged, non-root user contexts (`USER 1000:1000`).
6. **Host Sandbox Confinement**: Executable verification criteria and model-generated shell commands are confined within Linux unprivileged namespaces via `bubblewrap` (`bwrap`), enforcing unshared namespaces, cleared environment, read-only repository and system mounts, zero network egress, and isolated POSIX process groups. The host sandbox's `/tmp` is a private 64 MiB tmpfs mounted nosuid and nodev, which the confined command can write to and execute from, because bubblewrap has no noexec option for a tmpfs.
7. **Review Tool Execution**: A review starts its tools through a `ToolExecutor` (`src/devops_cli/security/tool_executor.py`). The tools are Bandit, Gitleaks, Semgrep, Trivy, kube-linter, Pluto, osv-scanner, golangci-lint, Ruff, mypy and the canary of each. The record of each run names the executor in force. It is the `executor` field in `tool_runs` of `profile.json`, and the Executor column of the Tool Runs table in `review.md`. Two executors exist:
   - `sandbox` is `SandboxToolExecutor`, and it is the default of `devops review path`, `branch` and `pr` and of their MCP tools. It runs the tool in a `bubblewrap` sandbox with no network, a cleared environment, a read-only tree and a private HOME. The sandbox shows the system directories, the tree and only what the request names: the program of the tool (its virtualenv, with the Python installation that the virtualenv links to, behind the guard of `HostSandbox`), its config and ruleset files, the data that a fetch step got before (the Trivy cache and the osv-scanner database, read-only) and the host paths in `CONST_TOOL_HOST_READ_ONLY_PATHS` (the CA certificates for Semgrep). A directory that the tool writes, the cache of mypy or of Ruff for the tree, is bound read-write. The sandbox refuses a bind that holds the home directory or the tree, or passes through a credential directory. Each process of the tool has the CPU limit `CONST_TOOL_CPU_LIMIT_SECONDS` and the address-space limit `CONST_TOOL_MIN_ADDRESS_SPACE_BYTES`. Gitleaks and Semgrep get the larger value that `CONST_TOOL_ADDRESS_SPACE_BYTES` names, and Semgrep runs `CONST_SEMGREP_JOBS` jobs. A Go tool gets `GOMEMLIMIT` set to `CONST_TOOL_GO_MEMORY_LIMIT`. The wall-clock limit applies as well. The sandbox sets no limit on the number of processes, because `RLIMIT_NPROC` counts every process of the user and would starve the host.
   - `direct` is `DirectToolExecutor`. It starts the tool as a child process of devops-cli. It has no confinement: the tool has the network, the environment and the files of the user. It has no limit except the wall-clock time of the scan, `DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS`. A review never uses it: no option, config key or MCP tool turns the sandbox off (decision 1 of #772). The scans of `devops scan`, `devops k8s audit` and the agent tools are not reviews, and they use this executor.

   Before its first tool runs, a review checks that the host can start the sandbox: bubblewrap and `prlimit` are installed, and bubblewrap can make a sandbox. On Ubuntu 24.04 and later, AppArmor refuses unprivileged user namespaces to a program that has no profile with the `userns` rule (`kernel.apparmor_restrict_unprivileged_userns`). A host that fails the check fails closed: no tool runs, in the sandbox or outside it, each scan reports a coverage gap with the cause, and the review says the cause and what a person can change on the host one time. The record is read before the tool starts. Under the `direct` executor, a tool that fetches its rules during the run, such as Trivy with an old cache, may use newer rules than the record names, and Ruff also applies a config file above the tree and its user config file, which the record does not name.
8. **Repository Hygiene**: Never write an internal hostname (`*.lan`, `*.local`, a machine name), a private address (RFC 1918), a private registry, a non-standard NodePort, a device or mount path, or the cluster topology into a committed file. Use `<storage-node>`, `<gpu-node>`, `<worker-node>` or `<host>` for a host, RFC 5737 blocks (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) or loopback for an address, `ghcr.io/<org>/<image>:<tag>` for a registry and `<storage-mount-path>` for a path. Committed templates (`config.example.yaml`) use localhost endpoints. The user's `config.yaml` is not committed: never reset its URLs or ports.
9. **No Phone-Home**: Turn off third-party telemetry, usage reports, crash analytics and update checks in every tool, workload and container when the user loses no function. Examples are `DO_NOT_TRACK=1`, `GOTELEMETRY=off`, `PIP_DISABLE_PIP_VERSION_CHECK=1`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `HF_HUB_DISABLE_TELEMETRY=1` and `OPENSPEC_TELEMETRY=0`. Ask the user before you turn off a feature that shows content, such as update notices or a marketplace.
10. **Bounded Error Detail**: Cap each external value in an exception `details` dictionary or a structured log at 256 characters (CWE-209, CWE-400).

---

## Reporting a Vulnerability

We deeply appreciate responsible security disclosures. If you discover a security vulnerability within DevOps CLI:

1. **Do NOT open a public issue, pull request, or discussion.**
2. Report the vulnerability privately via **[GitHub Security Advisory](https://github.com/dan-petty/devops-cli/security/advisories/new)**.
3. If you cannot use GitHub Security Advisories, contact the project maintainers directly via email at `contact@danielpetty.com` with the subject prefix `[SECURITY VULNERABILITY]`.

### What to Include
To help us triage and remediate the issue rapidly, please include:
- A detailed description of the vulnerability and its potential impact.
- Affected component or CLI subcommand.
- Step-by-step reproduction instructions or a minimal Proof of Concept (PoC).
- Any proposed remediation or mitigation steps.

---

## Response & Remediation SLA

- **Initial Triage & Acknowledgment**: Within **24 hours** of receipt.
- **Vulnerability Assessment & Severity Rating**: Within **48 hours** using CVSS v3.1 scoring.
- **Patch Development & Release**: Critical security fixes merge into `main` and ship in a release within **72 hours** of triage confirmation.
- **Public Disclosure**: Coordinated after the patch release is confirmed and deployed.

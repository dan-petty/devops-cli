# Security Policy — DevOps CLI

DevOps CLI follows an enterprise zero-trust security model designed to safeguard developer workstations, local and remote Kubernetes clusters, CI/CD pipelines, and agentic AI execution environments.

---

## Supported Versions

Security updates and critical vulnerability fixes are applied to the active release stream.

| Version | Supported | Security Policy |
| :--- | :--- | :--- |
| `0.2.x` | :white_check_mark: | Full active security support & rapid patch cycle |
| `0.1.x` | :x: | End of Life (upgrade to `0.2.x`) |
| `< 0.1.0` | :x: | Unsupported prototype releases |

---

## Zero-Trust Security & Egress Safety Principles

All code authored in or evaluated by DevOps CLI must strictly adhere to the following security guarantees:

1. **Zero Secret Leakage**: Plaintext secrets, tokens, private keys, or API credentials must never be committed to code repositories, written to unencrypted configuration files, or emitted into terminal outputs/logs. All sensitive values are managed through OS Keyring or HashiCorp Vault.
2. **Strict Egress & SSRF Protection**: All outbound network requests originating from AI models, documentation crawlers, or Kubernetes API clients must validate destination endpoints against private/loopback IP address ranges to prevent Server-Side Request Forgery (SSRF).
3. **Subprocess Bounded Execution**: All external commands (`git`, `helm`, `kubectl`, `tofu`, `docker`) are executed via bounded argument lists (preventing shell injection) with mandatory non-infinite timeouts.
4. **Data Isolation**: Agent-generated review logs, benchmarks, and temporary telemetry artifacts are isolated under dedicated agent subfolders (`<data_dir>/agent`, e.g. `./.data/agent`), completely segregated from the primary user workspace data tier (`DEVOPS_CLI_DATA_DIR` / `data.dir`).
5. **Least Privilege Runtime**: Kubernetes pods, Docker containers, and CI jobs run under unprivileged, non-root user contexts (`USER 1000:1000`).
6. **Host Sandbox Confinement**: Executable verification criteria and model-generated shell commands are confined within Linux unprivileged namespaces via `bubblewrap` (`bwrap`), enforcing unshared namespaces, cleared environment, read-only repository and system mounts, zero network egress, and isolated POSIX process groups. The host sandbox's `/tmp` is a private 64 MiB tmpfs mounted nosuid and nodev, which the confined command can write to and execute from, because bubblewrap has no noexec option for a tmpfs.
7. **Review Tool Execution**: A review starts its tools through a `ToolExecutor` (`src/devops_cli/security/tool_executor.py`). The tools are Bandit, Gitleaks, Semgrep, Trivy, kube-linter, Pluto, osv-scanner and Ruff. The record of each run names the executor in force. It is the `executor` field in `tool_runs` of `profile.json`, and the Executor column of the Tool Runs table in `review.md`. Two executors exist:
   - `direct` is `DirectToolExecutor`, and it is the default. It starts the tool as a child process of devops-cli. It has no confinement: the tool has the network, the environment and the files of the user. It has no limit except the wall-clock time of the scan, `DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS`.
   - `sandbox` is `SandboxToolExecutor`. It runs the tool in a `bubblewrap` sandbox with no network, a cleared environment, a read-only tree and a private HOME. Each process of the tool has the CPU limit `CONST_TOOL_CPU_LIMIT_SECONDS` and the address-space limit `CONST_TOOL_MIN_ADDRESS_SPACE_BYTES`. A Go tool gets `GOMEMLIMIT` set to `CONST_TOOL_GO_MEMORY_LIMIT`. The wall-clock limit applies as well. The sandbox sets no limit on the number of processes, because `RLIMIT_NPROC` counts every process of the user and would starve the host.

   A review runs its tools with the `direct` executor until a later change makes the sandbox the default. The record is read before the tool starts. A tool that fetches its rules during the run, such as Trivy with an old cache, may use newer rules than the record names. Under the `direct` executor, Ruff also applies a config file above the tree and its user config file, and the record does not name them.

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
- **Patch Development & Release**: Critical security fixes will be published to `main` and active release branches within **72 hours** of triage confirmation.
- **Public Disclosure**: Coordinated after the patch release is confirmed and deployed.

Perform a specialized configuration review on '{target}'.

### Configuration Review Mandates:
- **Security Hardening & Least Privilege**: Detect dangerous container privileges (`privileged: true`, `allowPrivilegeEscalation: true`, root user `runAsUser: 0`), host namespace sharing (`hostNetwork`, `hostPID`), unencrypted communication schemes (`http://` instead of `https://`), exposed debug ports, and hardcoded secrets, passwords, or API keys.
- **Schema & Syntax Conformance**: Validate structured syntax (YAML, JSON, TOML, HCL, INI, Dockerfile directives), mandatory schema properties, type correctness, and absence of obsolete, deprecated, or unrecognized configuration directives.
- **Operational Resilience & Resource Bounds**: Ensure containers and workloads specify bounded CPU and memory requests/limits to prevent resource starvation; verify liveness/readiness probes, proper restart policies (`restartPolicy`), health checks, and log rotation parameters.
- **Immutable Provenance & Dependency Pinning**: Flag unpinned image tags (`:latest`), missing checksum digests, floating package versions, or untrusted third-party image repositories.
- **Remediation**: Output structured findings citing exact line locations (`path/to/file.yaml:start-end`), hardened drop-in configuration snippets, and isolated verification criteria.
- **Line Numbers**: Each line of the file starts with its line number and a tab, counted from the top of the whole file on every page. Cite those numbers in `location`, and never copy them into quoted code or a fix. In a diff, a removed line has no number.

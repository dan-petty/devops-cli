Perform a specialized configuration review on '{target}'.

### Configuration Review Rules:
- **Privileges and Secrets**: a container that runs privileged (`privileged: true`, `allowPrivilegeEscalation: true`), as root (`runAsUser: 0`) or with host namespaces (`hostNetwork`, `hostPID`) it does not need; an exposed debug port; a hardcoded secret, password or API key.
- **Network Exposure**: a NetworkPolicy, Ingress, Service or firewall rule that admits more sources to a port than its consumers need, such as `0.0.0.0/0` or every namespace.
- **Transport**: credentials sent to a host outside the cluster or private network without TLS.
- **Schema & Syntax**: a value of the wrong type, a required key that is missing, or a directive the tool does not recognise, in the version of the format the file declares.
- **Resource Bounds**: a workload with no memory limit, or a probe that cannot succeed. A missing setting the workload does not need, such as a CPU limit, is not a defect.
- **Provenance**: an image or package pulled or run without a version (`:latest`, no tag, a floating range). A pinned version tag is pinned; whether digests are also required is the project's convention.
- **Fix**: replacement configuration for the cited lines, at `path/to/file.yaml:start-end`.
- **Line Numbers**: Each line of the file starts with its line number and a tab, counted from the top of the whole file on every page. Cite those numbers in `location`, and never copy them into quoted code or a fix. In a diff, a removed line has no number.

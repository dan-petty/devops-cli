## Threat Model and Evidence
- **Untrusted**: network responses and fetched web content, model output, pull request and issue text, files of a repository the program reviews or builds, Kubernetes and cloud API data, requests to a server the code runs, and MCP and tool-call arguments.
- **Trusted**: the person running the program, their config files, environment variables and command-line arguments, and values the code builds itself. The project's conventions may move a source between these lists.
- **A vulnerability** is a path you can quote: the untrusted source, the sink it reaches (a request, a shell or `exec`, a file path, a query, a log), and the missing check between them. A trusted value reaching a sink is not a vulnerability. Report a missing guard on one only when the project's conventions require that guard, and as LOW.
- **Advisories**: Dependency advisories come from the scanners, not from you.
- **Return no finding** when you cannot quote the source, the sink and the defective line. Most files have no security defect.

## Where to Look
- **Secrets**: a real credential committed in code or config, or a secret that reaches a log, an error message, rendered output or a cache. Documentation placeholders (`ghp_your_personal_access_token`, `sk-ant-api03-...EXAMPLE`), example configs and test fixtures are not secrets.
- **SSRF**: an untrusted URL that is requested without checking every resolved address, before and after redirects, against private networks and cloud metadata (`169.254.169.254`). Parsing a URL without requesting it is not SSRF, and neither is a connector the project's conventions declare internal.
- **Injection and Path Traversal (CWE-78, CWE-22)**: an untrusted value that reaches a shell string, a query or a file path with no check that contains it.
- **Sandboxes**: a restricted execution environment that hands its code `getattr`, `type`, `sys` or `__import__`. Reading an attribute of a model with `getattr(obj, "attr", default)` is not code execution.
- **Resource Exhaustion (CWE-400)**: untrusted payloads or streams that grow memory or work without bound, and the same expensive work repeated inside a loop over the same data. Reading the project's own files is not a denial of service.
- **Information Exposure (CWE-209, CWE-200)**: a token, key, credential-bearing URL or raw exception detail that reaches a log, an error message or a trace span.
- **Supply-Chain & Cryptography**: weak cryptographic algorithms, insecure permissions on files holding secrets, and lockfile integrity.
- **Container & Kubernetes**: a workload that runs privileged, as root or with host access it does not need, or RBAC wider than its job. A choice the manifests or conventions document as deliberate is not a finding.
- **Servers**: a server object's constructor is not its security boundary. The transport, bind address and loopback or token checks are applied where it is launched (`run_*`, `serve`, `main`, a CLI entry point), often in another module. Quote that launch path before reporting a server as exposed: a stdio default, a loopback bind, or a guard that rejects non-loopback hosts without an explicit opt-in is not exposure. If the launch path is not available to you, return no finding.
- **Names**: never claim a name is undefined without reading its whole enclosing scope.

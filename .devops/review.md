# Review Conventions: devops-cli

`devops ai review` reads this file in full when it reviews this repository, and gives it to the
persona reviewers and to the verifier. It holds the rules that are true here and not in general.
The shared review prompts stay project-agnostic; see `docs/SELF_IMPROVEMENT.md`.

## Python and types

- The package requires Python 3.14 (`requires-python = ">=3.14"`). PEP 758's unparenthesized
  multi-exception clause (`except A, B:`) is valid here, and Ruff formats code that way.
- The package passes `mypy --strict`. A None-dereference claim against an attribute that is not
  declared Optional (`X | None`) at its definition is false, unless the value crosses an untyped
  boundary (`Any`, `getattr`, parsed JSON, `**kwargs`).

## What this tool is

A DevOps CLI reaches internal infrastructure and prints what it is working on. Both are its
purpose, not defects.

- **Internal connectors**: SSRF claims against infrastructure connectors that set
  `allow_private_network=True` (Valkey, the Vault broker, the Kubernetes API, Prometheus, Grafana,
  a local Ollama) are not defects. SSRF applies to user-supplied external URLs: web fetchers,
  document retrievers, user webhooks.
- **Console output**: information-exposure (CWE-200) claims about terminal output, debug logging
  of paths under inspection, or progress indicators are not defects.
- **Local input**: CWE-400 claims about reading repository files (`pyproject.toml`, schemas,
  markdown, lockfiles, local config) or building output collections during a CLI run are not
  defects.

## Documentation and configuration

- A concrete RFC 1918 address (`10.x`, `172.16-31.x`, `192.168.x`) or a real `.local` or `.lan`
  host name in published documentation, `k8s/` manifests or tests is a finding: use abstract
  roles (`<storage-node>`, `<gpu-node>`) instead.
- A NetworkPolicy that opens broad RFC 1918 ranges to sensitive ports without namespace scoping is
  a finding.

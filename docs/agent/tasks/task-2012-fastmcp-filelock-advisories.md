# Task: fastmcp 4.1.2 and filelock 4.2.4 Fix Seven Advisories (#2012)

**Issue**: [#2012](https://github.com/dan-petty/devops-cli/issues/2012)
**Scope**: scope/security
**Feasibility**: After #2006 merged, `uv audit` on `main` reported GHSA-vqqp-x5qm-5qp4 and GHSA-7xgj-8392-5q4r on `fastmcp` and `fastmcp-slim` 4.0.11 (fixed in 4.1.2), and GHSA-v4x8-3wr5-3wq8, GHSA-9vhv-jxww-xfm5 and GHSA-567q-5qvw-pf92 on `filelock` 3.32.6 (fixed in 4.2.1). `uv lock` resolves `filelock` 4.2.4 within the limits of `tldextract` and `virtualenv`.

## Description
`pyproject.toml` pins `fastmcp==4.1.2`, and `uv lock --upgrade-package fastmcp --upgrade-package fastmcp-slim --upgrade-package filelock` moves the lockfile. The lock also moves `openapi-pydantic` to 0.6.0, and it adds `beartype` 0.23.1 for Python 3.15 and later only; Python 3.14 keeps 0.22.9. The knowledge base names the new `fastmcp` version.

## Acceptance Criteria
- [x] `uv.lock` holds `fastmcp` and `fastmcp-slim` 4.1.2 and `filelock` 4.2.4.
- [x] `uv run devops ci audit` passes, and the 368 MCP and domain tests pass on the new versions.

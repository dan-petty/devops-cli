# Task: The Lockfile Moves virtualenv Past Four Advisories That Fail the Audit Check (#1790)

**Issue**: [#1790](https://github.com/dan-petty/devops-cli/issues/1790)
**Scope**: scope/ci
**Feasibility**: The Static Analysis job's `uv audit` of run 39640348331 reported "virtualenv 21.14.1 has 4 known vulnerabilities", all fixed in 21.14.7, among them GHSA-vxj4-q4g9-crj7 (virtualenv's bash activate script runs commands from an environment name with a backslash before `$`). `uv tree --invert --package virtualenv` shows virtualenv comes in only through `pre-commit`, in the dev group. `uv audit` over the upgraded lock found no known vulnerability.

## Description

- [x] `uv lock --upgrade-package virtualenv` moves `virtualenv` from 21.14.1 to 21.14.12, and its helper `python-discovery` from 1.6.0 to 1.6.4. No other package changes, and `pyproject.toml` is unchanged.
- [x] `uv audit` reports no known vulnerability, and `uv lock --check` passes.

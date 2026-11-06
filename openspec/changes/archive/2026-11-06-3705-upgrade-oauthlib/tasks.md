# Tasks

## 1. Update

- [x] Run `uv lock --upgrade-package oauthlib`
  - Verification: `uv audit --frozen` finds no vulnerability
- [x] Check the lock and the audit
  - Verification: `uv lock --check` and `uv audit --frozen` pass

# Tasks

## 1. Audit

- [x] 1.1 List the failed steps of every run attempt of each Renovate pull request since 2026-11-16 20:00Z, with the cause and the item that fixes it
  - Verification: the Actions API of each run (`jobs?filter=all`) and the log of each failed job; the table is in design.md

## 2. Renovate configuration

- [x] 2.1 Give each update of a file under `src/devops_cli/`, the groups `uv`, `node`, `python runtime` and `bandit`, and lock file maintenance the prefix `fix(deps):` in `.github/renovate.json`
  - Verification: `$ npx --yes --package renovate@44.239.1 renovate-config-validator --strict --no-global .github/renovate.json .github/renovate/base.json`
- [x] 2.2 Resolve the prefix of one update of each member of the affected groups with Renovate's `applyPackageRules`, on `main` and on this change
  - Verification: a script outside the repository; the result is in design.md

## 3. Documents

- [x] 3.1 Name the prefix rule, and the checks that run on a Renovate pull request, in `docs/SDLC.md`
  - Verification: `$ uv run devops ci docs`

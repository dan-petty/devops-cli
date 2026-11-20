# Tasks

## 1. Config

- [x] 1.1 Turn on Renovate automerge for minor, patch and digest updates in `.github/renovate/base.json`
  - Verification: `$ npx --yes --package renovate@44.239.2 renovate-config-validator --no-global .github/renovate/base.json .github/renovate.json`

## 2. Documents

- [x] 2.1 Name the second exception in `AGENTS.md`, and the rule in `docs/SDLC.md`, `docs/CLUSTER.md` and the description of `.github/renovate.json`
  - Verification: `$ uv run devops openspec check`

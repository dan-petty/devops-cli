# Tasks

## 1. Delete the forwarding preset

Kind: other (deletion). Reads: `.github/renovate/base.json`, the Renovate config of each dan-petty repository. Changes: `.github/renovate/base.json`.

- [x] 1.1 Confirm that no dan-petty repository outside devops-cli names the old path `devops-cli//.github/renovate/base`
  - Verification: `$ uv run devops gh api -X GET search/code -f q='devops-cli//.github/renovate/base user:dan-petty' --jq '[.items[].repository.full_name] | unique'` prints only `dan-petty/devops-cli`
- [x] 1.2 Delete `.github/renovate/base.json`
  - Verification: `$ test -z "$(git ls-files .github/renovate/base.json)"` exits 0

## 2. Check the documents and specs

Kind: other (documents). Reads: each file that names `renovate/base`. Changes: none.

- [ ] 2.1 Make sure that no file outside the archived changes names the old path
  - Verification: `$ ! git grep -n 'devops-cli//.github/renovate/base' -- . ':!openspec/changes/archive'` exits 0
- [ ] 2.2 Make sure that the documents and the specs pass their checks
  - Verification: `$ uv run devops ci --check --only docs,openspec` passes

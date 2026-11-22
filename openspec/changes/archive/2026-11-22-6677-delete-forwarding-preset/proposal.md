# Proposal: #6677

## Why
Closes #6677. After #6676, `.github/renovate/base.json` holds only one `extends` entry, `github>dan-petty/infra//renovate/base`. It is a forward for the repositories that extended the old path `github>dan-petty/devops-cli//.github/renovate/base`. Each of these repositories now extends the infra preset directly, so the forward has no consumer.

## What Changes
- Delete `.github/renovate/base.json`. Then the folder `.github/renovate/` is empty, and git keeps no folder.
- No document, spec, test, check, workflow or generated file names the forward. #6676 changed each of them to the infra preset. Thus this change edits no other file.
- The change has no spec delta (`skip_specs: true`): no requirement of `openspec/specs/` names the forward, and no repository extends it. The Renovate pull requests of each repository keep the same rules, because each one gets the rules from `github>dan-petty/infra//renovate/base`.
- The change fits one pull request.

## Capabilities
- None. No requirement changes.

## Impact
- The shared Renovate rules have one home: `renovate/base.json` of dan-petty/infra.
- A repository that extends the old path gets a Renovate config error. On 2026-11-22 no repository of dan-petty extends it.

## Feasibility
- Consumers: on 2026-11-22 the contents API reads the Renovate config of each of the 18 non-archived repositories of dan-petty. dan-petty/danielpetty.com, dan-petty/devcontainer-features, dan-petty/devtools, dan-petty/vibes and dan-petty/devops-cli extend `github>dan-petty/infra//renovate/base`. dan-petty/infra extends `local>dan-petty/infra//renovate/base` and `local>dan-petty/infra//renovate/k8s`. dan-petty/meraki-dashboard-exporter has a `renovate.json` with no `github>` or `local>` preset. The 11 other repositories have no Renovate config.
- Code search: `devops gh api -X GET search/code -f q='devops-cli//.github/renovate/base user:dan-petty'` finds 6 files, all in dan-petty/devops-cli: `.github/renovate/base.json` and 5 files of archived changes.
- The merged pull requests are danielpetty.com for dan-petty/danielpetty.com#39, dan-petty/devcontainer-features#14, dan-petty/devtools#36 and dan-petty/vibes#299.
- Readers in devops-cli: `git grep -n -E 'renovate/base|devops-cli//' -- ':!openspec/changes/archive'` on origin/main `a3e30286e` finds the forward itself. Each other hit names the infra preset `github>dan-petty/infra//renovate/base` or `renovate/base.json` of dan-petty/infra. No file under `src/`, `tests/`, `.github/workflows/` or `.pre-commit-config.yaml` reads `.github/renovate/`.

## Existing Tool Considered
- Renovate preset `extends` (the `github>owner/repo//path` form) shares the rules with no code. The preset of dan-petty/infra holds them, and the CI job "Renovate presets" of infra checks it.
- The change deletes `.github/renovate/base.json`. It adds no code.

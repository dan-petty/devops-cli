# Proposal: #7482

## Why

#7482: `devops repos onboard` renders the Copier template of the setting `github.template_repository`. Its default was `dan-petty/infra`. On 2026-11-27 the owner gave the reusable workflows and the repository template to the new public repository `dan-petty/github-workflows` (dan-petty/infra#217).

That repository releases them with its own root tags, only when one of them changes. dan-petty/github-workflows#3 moved the files, and its first release v0.1.0 came on 2026-11-27. infra removes the template in a parallel pull request.

## What Changes

- The default of `github.template_repository` is `dan-petty/github-workflows` (`DEFAULT_GITHUB_TEMPLATE_REPOSITORY`). `uv run devops docs generate` writes `docs/CONFIGURATION.md` again.
- `docs/repos/onboard.md` and `docs/guidelines/production-readiness.md` name the new source.
- `docs/repos/onboard.md` tells how a repository with another `_src_path` takes the template from the new source.
- ADR 0032 and ADR 0035 each get one dated `Fact out of date` line in their Status History.

The change has no spec delta (`skip_specs: true`). The requirement "The baseline comes from the template at one ref" of `openspec/specs/repos-onboard/spec.md` names the setting, not its default. That requirement stays true. A default is a value of the configuration, and no spec scenario and no test holds such a value (docs/TESTING.md).

## Capabilities

None. The behavior of the capability `repos-onboard` does not change: it renders the template of `github.template_repository`.

## Impact

- With no `github.template_repository` in the configuration, `devops repos onboard` renders the template of dan-petty/github-workflows. The ref stays `--template-ref`, else `_commit`, else the latest release.
- A repository that infra onboarded holds `_commit: v0.25.3` and `_src_path` of infra. dan-petty/github-workflows has no such tag, so the baseline rows of that repository are `not readable`. The nightly Job `repos-drift` shows the same rows. They stay so until the repository takes the template from the new source with `copier recopy` (dan-petty/infra#217, step 5).
- The change fits one pull request.

## Feasibility

- `GET /repos/dan-petty/github-workflows/releases/latest` gave `v0.1.0`, published 2026-11-27T23:27:42Z. Its tree holds `copier.yml`, `templates/repository/` (23 files) and `templates/github-repository.schema.json`. `src/devops_cli/github/onboard/baseline.py` reads these files.
- On the base, `uv run devops repos onboard dan-petty/github-workflows --plan --only 9` printed `# Onboarding of dan-petty/github-workflows at v0.26.1`, the latest release of infra. With this change it printed `at v0.1.0`.
- In v0.1.0 the template renamed its hidden answer `infra_ref` to `template_ref` (`when: false`). `git grep -n infra_ref src/ tests/` finds no line, so no code of devops-cli gives that answer.
- `docs/service-repos.md`, the Renovate preset `renovate/base` and the Kustomize bases stay in infra. So `DOC_SERVICES_ENTRY`, `.github/renovate.json` and `k8s/devops/valkey-roadmap` keep their links to infra.

## Existing Tool Considered

Copier (MIT) renders the template and keeps the answers, and the change uses it as it is. The change sets one default value and builds nothing. It deletes no internal code.

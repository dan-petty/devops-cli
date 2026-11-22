# Proposal

## Why

The owner gave the design of one-command repository onboarding and four decisions on 2026-11-22 (#6773). Decision D1 gives the repository settings to the command `devops repos onboard`, with one baseline in dan-petty/infra. ADR 0026 decisions 1, 4 and 7 put these settings in OpenTofu code (#5311), so no record in force holds D1. D2 to D4 set the release flow of a private repository on the Free plan, the merge of the template pull request and the connection to the Service. The command of #6773 needs these decisions in a record before it is built (#6782).

## What Changes

- A new architecture decision record, `docs/adr/0035-the-onboard-command-owns-the-repository-settings.md`, that records D1 to D4 and amends ADR 0026 decisions 1, 4 and 7: the command owns the repository settings with one baseline in dan-petty/infra, and OpenTofu keeps the organization checks and the transfer check.
- ADR 0026 gets `amended-by: ["0032", "0035"]` and a dated `Status History` line that names ADR 0035.
- Row ACC-3 of `docs/guidelines/production-readiness.md` says that the command applies the repository settings and that OpenTofu holds the organization settings, because D1 makes the old row wrong.
- The index of `docs/adr/README.md` gains the row of the record and the new link of ADR 0026.
- The change writes no code and alters no behavior a consumer observes, so it carries no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The record is documentation, so the change carries no spec delta.

## Impact

- Documents: `docs/adr/0035-the-onboard-command-owns-the-repository-settings.md` (new), `docs/adr/0026-github-settings-are-opentofu-code-the-owner-applies.md`, `docs/adr/README.md`, `docs/guidelines/production-readiness.md`

## Feasibility

- The premise holds at main 8e99f1da6. The last record is ADR 0034. ADR 0026 is accepted and amended once (ADR 0032), so a second amendment is allowed (`docs/adr/README.md`, "Supersede a record").
- No prerequisite of ADR 0026 exists: devops-cli has no `tf/` folder, dan-petty/infra has no GitHub module under `tf/modules/`, dan-petty/homelab has no `tf/github/` stack, and the cluster has no `tofu-state` namespace (`kubectl get ns tofu-state` answers NotFound).
- The provider issue `integrations/terraform-provider-github#3664` (the `code_quality` rule of a ruleset) is open, so the provider cannot hold the `main` ruleset that the baseline keeps.
- No code applies a repository setting today: `apply_onboarding` of `src/devops_cli/roadmap/onboard.py:477` creates only missing labels.
- The setting `service.repos` (`src/devops_cli/config/settings.py:1802`), `devops k8s push-secrets` and `devops k8s deploy-stack` exist for D4.
- Row ACC-3 of `docs/guidelines/production-readiness.md` says that the repository settings are OpenTofu code, so the same change updates it (AGENTS.md rule 8). Row ACC-2 stays true, because a person runs the command.
- The form rules are those of `docs/adr/README.md`, checked by `tests/invariants/test_adr_records.py`, and `uv run devops docs generate` writes the index.

## Existing Tool Considered

The record needs no tool: MADR 4 is the form, and the repository already holds the records and their check (`src/devops_cli/docs/adr_records.py`). For the decision itself, ADR 0026 considered OpenTofu with `integrations/github` and safe-settings 3.0.0. OpenTofu keeps the organization checks and the transfer check, and its rejection of safe-settings stays in force. The written cost of the record is about 8,000 tokens and about 1 hour.

## Dependencies

- ADR 0026 and ADR 0032, in `docs/adr/`, done.
- Owner design and decisions D1 to D4 of 2026-11-22, on #6773, done.

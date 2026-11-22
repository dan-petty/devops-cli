# Design

## Decisions
- **Delete the forward now.** #6676 kept `.github/renovate/base.json` as a forward until each repository that extended the old path changed its `extends` line. On 2026-11-22 each of these repositories extends `github>dan-petty/infra//renovate/base` on `main` (contents API of each repository), and a code search finds the old path only in devops-cli. Thus the gate of the issue holds.
- **No spec delta.** No requirement of `openspec/specs/` names `.github/renovate/base.json` or the old path. The specs of #6676 name only the infra preset. The deletion removes no rule that a repository uses, so no observable behavior changes.
- **Archived changes stay as they are.** The archived changes of #4896, #4905, #6118 and #6676 name the old path. They record the history of the plan, so this change does not edit them.

## Rejected alternatives
- **Keep the forward for unknown consumers.** The Renovate App of the cluster reads only the repositories of its installation, and the GitHub Apps are on all dan-petty repositories. The contents API shows that no such repository extends the old path. A copy that no consumer uses is a second home of the rules that ADR 0032 removes.
- **Keep an empty preset with no `extends`.** A repository that extended it would get no shared rules and no error. That hides a config fault. A missing preset gives a Renovate config error that a person sees.

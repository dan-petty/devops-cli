# Design

## Context

The repository is public, so `devops k8s deploy-stack` writes the homelab hosts onto the Argo CD Applications `devops` and `ingress` as Kustomize patches in `spec.source.kustomize` (#1290). Argo CD Image Updater writes the Service image digest into `spec.source.kustomize.images` of `devops`. The app-of-apps `cluster` ignores that field in its diff and has the sync option `RespectIgnoreDifferences=true`. A manual sync of `cluster` without that option deleted the overrides on 2026-10-21 (#1817).

## Goals / Non-Goals

**Goals:**

- A sync of `cluster`, automated or by hand, keeps the overrides, whichever sync options it has.
- An alert fires when a live Ingress routes a host under the placeholder domain.
- `k8s/README.md` tells which actions still remove the overrides and how to set them again.

**Non-Goals:**

- Move the values out of the Applications. #1291 does that, after #1082.
- Write the overrides back automatically. The check only reads.
- Change `k8s/gitea/` or the Gitea Applications.

## Decisions

- **Decision: apply the two Applications server-side with the per-resource annotation.**
  *Choice:* `argocd.argoproj.io/sync-options: ServerSideApply=true` on `devops` and `ingress` in git.
  *Rejected Alternative:* only a README rule that `cluster` is not synced by hand without Respect Ignore Differences (the first remedy of the issue).
  *Evidence for Rejection:* the rule depends on a person each time. The multi-app sync panel sends one list of options for all selected Applications, and an empty list replaces the options of the spec (`server/application/application.go` `Sync`).
- **Decision: keep `RespectIgnoreDifferences=true` on `cluster`.**
  *Rejected Alternative:* remove the option, so that the last-applied annotation does not hold the overrides.
  *Evidence for Rejection:* the live annotation holds them now, so the next client-side sync after the removal deletes them. The ignored pre-delete and post-delete finalizers of #1674 also need the option on the Applications that `cluster` applies client-side.
- **Decision: the per-resource annotation, not an option of `cluster`.**
  *Rejected Alternative:* `ServerSideApply=true` in `spec.syncPolicy.syncOptions` of `cluster`.
  *Evidence for Rejection:* that is an option of the operation, and a manual sync can omit it as it omitted `RespectIgnoreDifferences=true`. Only the resource annotation is read in every sync (`shouldUseServerSideApply`).
- **Decision: no `managedFieldsManagers` entry in `ignoreDifferences`.**
  *Rejected Alternative:* ignore the fields of `kubectl-patch` and Image Updater by field manager.
  *Evidence for Rejection:* `ignoreDifferences` changes the diff, and the sync only through `RespectIgnoreDifferences=true`, which a manual sync can omit.
- **Decision: set `argocd-controller` as the client-side apply migration manager of `cluster`.**
  *Rejected Alternative:* keep the default manager `kubectl-client-side-apply`.
  *Evidence for Rejection:* no live entry has that name. The entry of the old client-side apply is `argocd-controller` with operation `Update`, and it keeps its fields after the change to server-side apply. A field that git removes from the two Applications then stays in the cluster.
- **Decision: a Prometheus alert, not a new `devops k8s` check.**
  *Rejected Alternative:* a command that reads the live Ingresses or the Applications.
  *Evidence for Rejection:* the existing alert rules, with a test entry, cover the symptom with no new code, and they fire with no person present. `kube_ingress_path` gives the host of each Ingress rule.
- **Decision: severity `critical`, 5 minutes.**
  *Choice:* every public host fails at the same time, and the overrides do not come back without a person. 5 minutes is longer than a deploy-stack run that writes the patches.

## Risks / Trade-offs

- A sync of `cluster` with Replace and without Respect Ignore Differences replaces the Applications with git and deletes the overrides. A recreated Application has no overrides. `k8s/README.md` names both, and the alert fires.
- The alert does not see the IngressRoute with a host match, because kube-state-metrics does not serve IngressRoutes. A lost override set changes all Ingresses at the same time, so the alert fires.
- The alert fires also for a host that git adds before deploy-stack sets its patch. That host returns 404 too, and deploy-stack is the fix.
- The tests read files. Only the cluster shows the first server-side sync. A person checks the managed fields after the merge (tasks.md).

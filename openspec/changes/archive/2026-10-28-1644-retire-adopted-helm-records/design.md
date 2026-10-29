# Design

## Decisions

### A command of its own, not a step of `bootstrap-gitops`

The issue proposed that `devops argo cd apps bootstrap-gitops` offer the retirement. `bootstrap-gitops` applies the root Application and returns. Argo CD adopts each chart later, when it syncs that chart's Application. At bootstrap time no release qualifies yet, so the step would always plan nothing. In Recovery, the record that `helm upgrade --install argocd` writes qualifies only after Application `argocd` syncs again. So the retirement is the separate command `devops argo cd apps retire-helm-records`, which a person runs after the Applications sync. `k8s/README.md` names it at the end of both procedures.

### What makes a release qualify

1. **An Application renders the release.** A source of the Application has a `chart`. The release name is that source's `helm.releaseName`, or else the Application's name, as Argo CD documents. The namespace is the Application's destination namespace. A record of any other release stays: nothing else renders it.
2. **Argo CD applied each top-level object of the release.** The command lists the live objects of every kind that `kubectl api-resources --verbs=list,create` names, events left out, and takes the top-level ones, with no owner reference, that carry the release's annotations `meta.helm.sh/release-name` and `meta.helm.sh/release-namespace`. Each one must carry the Application's tracking id (`<application>:...`), or name `argocd-controller` as a field manager.
3. **No owner reference on the record.** An operator such as the Alloy operator writes those records and keeps them.

When condition 2 fails, the plan names each object that Argo CD did not apply. Then a person syncs that Application, or finds why its objects are not Argo CD's, and runs the command again.

### Reads hold no Secret data

The records are Secrets that hold the release payload, and that payload holds the chart's rendered Secrets. The command reads them with a `jsonpath` of `metadata` fields only, so kubectl prints no `data`, and the process never sees it. The object listing uses the same kind of `jsonpath`.

### Delete by name

`--confirm` deletes the records that the plan names, one `kubectl delete secret -n <namespace> --ignore-not-found <names>` request for each release. It does not delete by label selector. A record that Helm writes after the plan stays, and the next run plans it.

## Rejected alternatives

- **Tracking id only.** This was the issue's own check. On the cluster, none of the 53 CRDs carries a tracking id. The Argo CD CRDs show `argocd-controller` as a field manager with operation `Apply`, so Argo CD applies them but does not stamp them. A tracking-id rule would refuse release `argocd` forever.
- **A successful sync after the newest record (`status.history`).** Argo CD's auto-sync does not run while an Application is Synced. `prometheus-operator-crds` is Synced with an empty history, so this rule catches that case. But a sync with `ApplyOutOfSyncOnly` skips the objects that are in sync, so a history entry does not prove that every object was applied. The object check proves it.
- **The release manifest from `helm get manifest`.** This gives the exact object list of a release. But it decodes the release payload, which holds the chart's rendered Secret values. The annotation listing finds the same top-level objects from their metadata.
- **Narrow the listing with the label `app.kubernetes.io/managed-by=Helm`.** Not every object that Helm stamps carries that label, so the selector would miss objects. One listing of all objects took 8.8 s on the cluster.
- **Keep the AppProject orphan ignore.** It hides a left-over record, such as the one that Recovery's `helm upgrade --install argocd` writes. Without the ignore, Argo CD warns about each left-over record. The Alloy records have an owner reference, so the orphan check skips them.
- **Delete with the label selector `owner=helm,name=<release>`.** It would also delete a record that Helm writes between the plan and the delete, and that record was never checked.

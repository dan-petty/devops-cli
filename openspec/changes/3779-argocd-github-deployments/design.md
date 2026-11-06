# Design

## Decisions

- **Add the block `github.deployment` to the existing template `app-deployed`.**: A notification template holds one block for each service, and a service reads only its own block. So the trigger `on-deployed` keeps one template, and the Mattermost subscription is unchanged.
- **Subscribe with an annotation on each Application, not with `notifications.subscriptions`.**: A global subscription reaches every Application, and a multi-source Application has no `spec.source` for the notifier to read. The annotation form is the one that `k8s/argocd/apps/devops.yaml` already uses for Mattermost, and a test derives the annotated set from the files.
- **Annotate the Applications of `k8s/argocd/apps/` with one GitHub source, and leave out `bootstrap` and `cluster`.**: Those two are the roots of the app-of-apps. A deployment named `cluster` or `bootstrap` says nothing about a workload.
- **Set `autoMerge: false` and `requiredContexts: []`.**: The defaults ask GitHub to merge the default branch into the ref and to wait for commit statuses. The App holds no permission for statuses, and a deployment of a synced commit must not write a branch.
- **Set no `logURL` and no `environmentURL`.**: `notifications.argocdUrl` is empty in git, and the host of Argo CD and of each workload is private configuration (SECURITY.md). A relative or placeholder URL would be wrong in the deployment.
- **Set `message` from the short sync revision, read with `dig`.**: The engine uses the message as the description of the deployment status. `dig` returns an empty value when a field is absent, so a missing revision cannot fail the template.
- **Leave the network policy as it is.**: Its egress rule 4 allows TCP 443 to any address except the metadata address.

## Rejected alternatives

- **A global subscription of `on-deployed` to `github`.**: The default `repoURLPath` and `revisionPath` read `.app.spec.source` and `syncResult.revision`. A multi-source Application sets neither, so each of its deploys would log a template error.
- **A selector on a label in `notifications.subscriptions`.**: The Applications carry no label for this, and a new label is a second place that names the same set as the annotation.
- **Set `repoURLPath` and `revisionPath` to read the first of `spec.sources`.**: The first source of a multi-source Application is a Helm chart repository, and the commit of a deployment must be the commit of this repository. That needs a rule for which source is the repository: more template code than the engine's default.
- **Add the failure states and a commit status of #2003.**: The App holds only the permission Deployments. A commit status needs another permission, which only a person grants.

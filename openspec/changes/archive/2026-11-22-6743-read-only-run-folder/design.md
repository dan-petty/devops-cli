# Design

## Decisions
- **No scratch folder.**: `publish` needs only a new repository of its own, and the temporary folder is its own in each shape.
- **The dry run reads git.**: it reads no cluster, so it takes the shape of the template from the manifests of the checkout with `phase_containers`, as `build_job` reads the CronJob.
- **The reason goes in the state.**: the Service reads the log of `publish` when the pod succeeds, so `publish` prints the reason that `prepare` wrote.

## Rejected alternatives
- **Choose the dry-run shape from the template name.**: Rejected: it is wrong before the switch of #3700.
- **Keep the data folder for the fix-checks publish.**: Rejected: one folder rule for every publish is simpler.

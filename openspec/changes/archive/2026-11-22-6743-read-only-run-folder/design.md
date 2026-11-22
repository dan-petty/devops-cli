# Design

## Decisions
- **No scratch folder.**: `publish` needs only a new repository of its own, and the temporary folder is its own in each shape.
- **The dry run shows both shapes.**: it reads no CronJob, so it cannot know the shape; it shows the create of each shape under its condition, as its follow steps do.
- **The reason goes in the state.**: the Service reads the log of `publish` when the pod succeeds, so `publish` prints the reason that `prepare` wrote.

## Rejected alternatives
- **Choose the dry-run shape from the template name.**: Rejected: it is wrong before the switch of #3700.
- **Read the shape from the manifests of the checkout.**: Rejected: a local manifest can differ from the CronJob of the cluster, and the place of the manifests moves with #5120.
- **Keep the data folder for the fix-checks publish.**: Rejected: one folder rule for every publish is simpler.

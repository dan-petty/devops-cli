# Design

## Decisions

- **Pin every version option of the two features in the image config, and leave the workspace config alone.**: The workspace config names the published image and holds no feature, and the image config holds the 4 `latest` values that start the lookups, so one file carries the whole change.
- **Set the kubectl and Helm options to the releases that the tools lock already pins.**: The image already installs both at those versions, and the invariant of the image build compares the tools lock with `.devcontainer/Dockerfile`; one pin per tool keeps the two copies equal.
- **Match the Compose option by a name that ends with `ComposeVersion`.**: `search_code` found neither `dockerComposeVersion` nor a variant in the tree, so the exact spelling comes from the metadata of the feature at implementation time, and the test pins no spelling that it cannot check.
- **Refuse the value `latest` on every option of every feature, instead of listing the options that accept a version.**: The test cannot tell which option accepts a version, and `latest` is the value that starts a lookup; the 9 other option values of the image config name a boolean, a user, a uid or the Node major and pass.
- **Keep the check in `tests/invariants/test_devcontainer_config.py`.**: That module already reads both configs and `Tests & Coverage` runs it; `devops devcontainer validate` reads one workspace config of any repository, so the pinning rule of this repository does not belong there.
- **Change no lockfile.**: Each lockfile entry is the digest of a feature artifact, which an option value does not change, and the frozen build keeps reading the same digests.
- **Add no check of a download inside the image build.**: Such a check needs the network during the build and cannot be asserted offline; the pinned release with its published checksum file gives the failure, and the invariant names a missing pin before the build starts.
- **Bump the options in a pull request that changes the config and the lockfile together.**: Renovate's devcontainer manager updates a feature tag and writes the lockfile, and no manager reads a feature option, so a bump is one reviewed diff of `.devcontainer/image/devcontainer.json`.

## Rejected alternatives

- **Keep `latest` and retry the image build step.**: A retry repeats the keyserver call and the release lookup; the three attempts of the issue failed in two different ways, so a retry hides the cause.
- **Install Minikube in `.devcontainer/Dockerfile` and drop the kubectl-helm-minikube feature.**: The Dockerfile already installs kubectl and Helm, and the tools lock holds no Minikube entry, so a Minikube step adds a pin and a checksum that no lock or test of the tree holds; the feature would still install its three tools unless its options change.
- **Pin only the Helm option.**: It leaves the kubectl, Minikube and Docker lookups and the Compose download, which is the second failure of the issue.
- **Add a step to the `devcontainer` job of the DevContainer Image workflow.**: That step runs after the build, so the failure it reports comes after the download that it would prevent, and the invariant runs in a required check on the same pull request.

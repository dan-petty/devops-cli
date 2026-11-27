## ADDED Requirements

### Requirement: An untagged image of a Plan takes the version of the Plan
For an object with `apiVersion: upgrade.cattle.io/v1` and `kind: Plan` that sets `spec.version`, the check SHALL read the image of `spec.prepare` or `spec.upgrade` that names no tag and no digest as `<image>:<version>`, where `<version>` is `spec.version` with each `+` replaced by `-`, as system-upgrade-controller pulls it. An image that names a tag or a digest SHALL keep it. A Plan that sets no `spec.version` SHALL give its images no tag.

#### Scenario: A Plan with a version
- **WHEN** a kustomization folder holds a Plan with `spec.version: v1.37.2+k3s1` and the untagged `prepare` and `upgrade` image `rancher/k3s-upgrade`, and the registry holds `rancher/k3s-upgrade:v1.37.2-k3s1`
- **THEN** `devops k8s image-pins <folder>` resolves the pin `rancher/k3s-upgrade:v1.37.2-k3s1` and exits 0

#### Scenario: A Plan with a channel and no version
- **WHEN** the Plan sets `spec.channel` and no `spec.version`
- **THEN** the image `rancher/k3s-upgrade` names `latest`, and `devops k8s image-pins <folder>` exits 1 and sends no request

#### Scenario: A Plan image with its own tag or digest
- **WHEN** the Plan sets `spec.version`, its `prepare` image names a tag and its `upgrade` image names a digest
- **THEN** each image keeps its own tag or digest

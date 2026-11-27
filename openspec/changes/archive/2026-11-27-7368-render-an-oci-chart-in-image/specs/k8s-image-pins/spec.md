## ADDED Requirements

### Requirement: A chart of an OCI registry renders by its OCI reference
`devops k8s image-pins` SHALL render a chart source whose `repoURL` has no `//` part, which is a path of an OCI registry, with `helm template <release> oci://<repoURL>/<chart>` and no `--repo`. The version, the namespace, `--skip-tests` and the value files SHALL be those of a chart source of an `http` or `https` chart repository, which SHALL render with the chart name and `--repo <repoURL>`. It SHALL take each `image` value of each render.

#### Scenario: A chart of an OCI registry
- **WHEN** the chart source of an Application names the `repoURL` `registry.example.com/charts` or `registry.example.com:5000/charts`, the chart `example` at `1.2.3`, and a value file of a ref source
- **THEN** `helm template` runs with the chart reference `oci://<repoURL>/example`, `--version 1.2.3`, the namespace, `--skip-tests` and the value file, with no `--repo`, and the image of the render is a pin of the Application

#### Scenario: A chart of an OCI registry that does not render
- **WHEN** `helm template` of such a chart source exits 1
- **THEN** the command stops with an `ImagePinError` that names the chart command and gives the error of Helm

#### Scenario: A dry run of a chart of an OCI registry
- **WHEN** a dry run reads a tree with such a chart source
- **THEN** the `helm template` command with the `oci://` reference is a planned command of the run, which the process runner prints and does not start, and the image of the chart is no pin of the run

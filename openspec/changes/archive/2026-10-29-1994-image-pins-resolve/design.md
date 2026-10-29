# Design

## Render as Argo CD renders

An Application's images are what Argo CD applies, so the command renders each source the way Argo CD does: `kubectl kustomize` for a path source (the builder that `check_argocd_gate` already uses) and `helm template <release> <chart> --repo <url> --version <v> --namespace <ns> --values <file>` for a chart source, with the release name `helm.releaseName` or the Application's name and each `$values/<path>` value file of the repository. A chart whose `repoURL` has no scheme is an OCI chart; no Application uses one yet, so the check stops and names it, and does not skip its images. A render that fails stops the check with helm's error: an empty list of images would pass a wrong pin.

The Applications render eight at a time, each in a directory of its own, because each `helm template` waits on the chart repository for most of its five seconds.

## Read the rendered YAML as Kubernetes does

`kubectl kustomize` reads the chart's output with the YAML library of Kubernetes and writes it again, and `yaml.compose_all` with the project's `YAML_SAFE_LOADER` (libyaml when present) reads that output as nodes. Composing builds no Python objects, so a scalar keeps its text whatever tag YAML 1.1 gives it. Each mapping's `image` key with a scalar value is an image. A CRD schema property called `image` has a mapping value and is not one.

## Which images are pins

- The repositories that an `ImageUpdater` object names (`spec.applicationRefs[].images[].imageName`) are moved by Image Updater, so an image of one of them is not a pin. The object is in a chart's rendered output, so a chart Application is rendered before the sort.
- An image of a registry that a runner cannot reach is not resolved: its registry host is an IP address (`ipaddress.ip_address`), `localhost`, a name with no dot (a Service in the cluster), or a name under `.svc`, `.cluster.local` or `.local`. It is listed, so a reader sees it.
- Each other image is a pin, resolved once whatever the number of Applications that name it.

## Resolve as an anonymous client

`docker buildx imagetools inspect <image> --format '{{json .Manifest}}'` runs with `DOCKER_CONFIG` set to an empty directory, because the cluster pulls without credentials and a stored credential that a registry refuses makes GHCR answer 403 for a public image. Exit 0 with a `digest` resolves the image. Any other result does not, with the tool's last error line as the reason. A registry's rate limit also fails the check, with the registry's own message: the check fails closed and never passes an image it did not see.

## Rejected alternatives

- **Path sources only (the refine block's answer).** It misses the five tags that value files set (`argo-workflows`, `gitea`, `open-webui`, `dcgm-exporter`, the Argo CD Valkey). Rendering the charts costs about 15 s in the job.
- **PyYAML or ruamel.yaml on helm's output.** Both refuse the `prometheus` chart's tab after a value, and would drop the Alertmanager StatefulSet's two images.
- **`crane digest` (HEAD, not counted by Docker Hub).** Better for the Docker Hub allowance; needs a new pin and a recording that this session could not make. Filed as #2610 with the measurements.
- **A row of `devops ci`.** The gate has no path field (`CheckSpec`), so every local gate and the pre-push hook would read the registries, and spend the Docker Hub allowance of the developer's network.
- **The Docker SDK for the reference split.** It ships no type information, and `src` is at its `type: ignore` ceiling; the ten-line split follows the grammar and a test holds it to the SDK.
- **Pass on a rate limit.** A check that passes when it could not read the registry is an escape; the job is not a required check, so a person re-runs it after the hour.

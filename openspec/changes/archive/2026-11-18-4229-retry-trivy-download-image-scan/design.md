# Design

## Decisions

- **Use `devops install-tools --tool trivy --only-missing` before each scan step**: Reuses the repository verified tool installer with retries and SHA-256 checks from `tools.lock`.
- **Set `skip-setup-trivy: "true"` on every image scan step**: Instructs `aquasecurity/trivy-action` to use the pre-installed Trivy binary on `PATH` and avoid downloading without retries.
- **Add `./.github/actions/setup-toolchain` in image jobs**: Provides the `uv` and Python environment needed to run `devops install-tools`. Set `save-uv-cache: "false"` to prevent Actions cache race conditions.
- **Keep `if` condition aligned in CI**: Ensure the toolchain setup and install steps in `ci.yml` have the same `if: steps.image_changes.outputs.changed == 'true'` condition as the scan step.

## Rejected alternatives

- **Add curl download with retry script in each job**: Duplicates `devops install-tools` logic and requires duplicating SHA-256 pins.
- **Retry the whole scan step**: Reruns the entire container scan and still lacks SHA-256 checks against `tools.lock`.

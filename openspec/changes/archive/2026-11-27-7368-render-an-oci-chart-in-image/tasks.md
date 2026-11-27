# Tasks

## 1. Render a chart of an OCI registry

Kind: behavior. Reads: `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/k8s/app_sources.py`, `src/devops_cli/k8s/catalog.py`, `src/devops_cli/core/process.py`, `tests/k8s/test_image_pins.py`. Changes: `src/devops_cli/k8s/image_pins.py`, `tests/k8s/test_image_pins.py`.

- [x] 1.1 In `tests/k8s/test_image_pins.py`, replace `test_an_oci_chart_repository_stops_the_check` with `test_a_chart_of_an_oci_registry_renders_by_its_oci_reference`, for a registry path with a port and with no port. Add `test_a_chart_of_an_oci_registry_that_does_not_render_stops_the_check_with_helms_error` and `test_a_dry_run_plans_the_command_of_a_chart_of_an_oci_registry_and_renders_nothing`
  - Verification: `$ uv run devops ci test tests/k8s/test_image_pins.py` fails on the base
- [x] 1.2 In `_chart_command` of `src/devops_cli/k8s/image_pins.py`, give Helm the chart reference `oci://<repoURL>/<chart>` for a registry path, and remove the refusal
  - Verification: `$ uv run devops ci test tests/k8s/test_image_pins.py tests/k8s/test_k8s_catalog.py` passes

## 2. Documents

Kind: other. Reads: `docs/CLUSTER.md`, `src/devops_cli/k8s/image_pins.py`. Changes: `docs/CLUSTER.md`, `src/devops_cli/k8s/image_pins.py`.

- [x] 2.1 Name the two repository forms of a chart source in the module text of `src/devops_cli/k8s/image_pins.py` and in the section "Image Pins" of `docs/CLUSTER.md`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- The dry-run plan of `devops k8s catalog` names the command of the run for each chart source: #7371.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

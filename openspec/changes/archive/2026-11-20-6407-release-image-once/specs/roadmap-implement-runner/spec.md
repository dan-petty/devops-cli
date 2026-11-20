## MODIFIED Requirements

### Requirement: The release publishes the runner image
The release SHALL build the `runner` target of `Dockerfile` one time, push it by digest as `ghcr.io/<repository>/runner`, run the smoke test on that digest, scan it with Trivy for HIGH and CRITICAL findings, attest its provenance, and tag the attested digest with the release tag and `latest`. `ci.yml` SHALL build, smoke-test and scan the same target on a pull request, push nothing, and run only when image content changed.

#### Scenario: The release workflow is read
- **WHEN** a person reads the `Runner Image` jobs of the first release after the merge with `uv run devops gh run view <run_id> --log`
- **THEN** `Build` pushed one digest, `Verify` started and scanned that digest, and `Attest & Tag` attested it and put the release tag and `latest` on it

#### Scenario: The pull request check is read
- **WHEN** a test reads `.github/workflows/ci.yml`
- **THEN** a job builds `target: runner` with `push: false` and `load: true`, and each of its build steps runs only if the image content changed

### Requirement: The smoke test of the runner image runs the tool check and bounds the size
The smoke test of the runner image in `ci.yml` and in the `Verify` job of `release-image.yml` SHALL be the same text, SHALL run the tool check of the image and the tool check of a copy of the checkout, SHALL then run `uv run ruff --version`, `uv run pytest --version` and `uv run mypy --version` in that copy, and SHALL fail when the image is larger than 7000000000 bytes.

#### Scenario: The smoke test runs on the loaded image
- **WHEN** the Runner Image job of `ci.yml` runs its smoke test on the loaded image
- **THEN** the check module prints that every runner tool is on PATH and runs, for the image and for the checkout, the three `uv run` commands exit 0, and the step fails when `docker image inspect` reports more than 7000000000 bytes

### Requirement: The scan of the runner image reports and stops no build
The Runner Image job of `ci.yml` and the `Verify` job of the runner image in the release SHALL scan the `runner` image with `.github/actions/image-scan` (Trivy, `HIGH,CRITICAL`, fixed findings only) with exit code 0, and SHALL upload the SARIF under the category `trivy-image-runner`. SECURITY.md SHALL record the exception in its table, with the scope, the compensating control, the evidence, the approval and the review.

#### Scenario: The scan of a runner image with findings
- **WHEN** the Runner Image job scans a runner image whose devtools tools hold fixed HIGH findings
- **THEN** the scan step exits 0, the job log names each finding, and code scanning lists them under `trivy-image-runner`

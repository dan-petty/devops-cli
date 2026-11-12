## MODIFIED Requirements

### Requirement: The scan of the third-party image only reports
The job `third-party-image-scan` of `.github/workflows/third-party-image-scan.yml` SHALL scan the image of the Deployment with Trivy at the version that `tools.lock` pins and SHALL exit 0 whatever it finds. The workflow SHALL run only for a pull request that changes `k8s/devops/crawl4ai/deployment.yaml` or the workflow file.

#### Scenario: The scan fails the job
- **WHEN** a test reads the workflow
- **THEN** the exit code of the Trivy step is 0 and the `paths` filter of the `pull_request` trigger names the Deployment

#### Scenario: A pull request that does not change the Deployment
- **WHEN** a pull request changes only `README.md`
- **THEN** the `paths` filter starts no run of the workflow

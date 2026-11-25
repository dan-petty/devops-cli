## ADDED Requirements

### Requirement: The release_comments row checks cluster images only for their repository
`_run_release_comments_adapter` SHALL check cluster Deployment and CronJob digests and query the OCI registry for `Live since <time>` comments only when the repository matches the repository named in `CONST_ROADMAP_RELEASE_IMAGE_PREFIX` (`dan-petty/devops-cli`). For every other repository, the round SHALL call `comment_releases` with `roll=None` and `client=None` so it posts `Released in <tag>` comments and updates `release_comments.json` with no cluster or registry request.

#### Scenario: An unrelated repository skips cluster and registry digest checks
- **WHEN** `run_release_comments_adapter` runs for `dan-petty/devtools` with a release published two hours before the round, an empty `RegistryFake`, and an empty `FakeCluster`
- **THEN** the closed issue referenced by the release receives one `Released in <tag>` comment and no `Live since` comment, `release_comments.json` records `released` true and `live` false, `web.sent` holds no registry request, and the round raises no error

#### Scenario: The image repository keeps cluster and registry digest checks
- **WHEN** `run_release_comments_adapter` runs for `dan-petty/devops-cli` with matching cluster Deployment and CronJob digests and matching `RegistryFake` manifests
- **THEN** the closed issue referenced by the release receives both its `Released in <tag>` and `Live since <time>` comments

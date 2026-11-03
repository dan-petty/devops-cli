# roadmap-release-comments Specification

## Purpose
What the roadmap Service says on an issue about the release that carries it: one comment when the release is out, one when the images of the release run in the cluster, and no write to a release, a tag or a file.

## Requirements

### Requirement: A release comments its version once on each closed issue it carries
The row `release_comments` SHALL post the comment `Released in <tag>` once on each closed issue that a pull request of a release closes. The pull requests are the numbers `(#N)` in the body of the release. The issues are the numbers after `Closes`, `Fixes` or `Resolves` at the start of a line in the body of each pull request. An open issue and a pull request get no comment.

#### Scenario: A release with two closed issues
- **WHEN** a release `v1.0.0` names pull requests 11 and 12, the body of 11 holds `Closes #101`, the body of 12 holds `Fixes #102`, and issues 101 and 102 are closed
- **THEN** issue 101 and issue 102 each hold exactly one comment that starts with `Released in v1.0.0`

#### Scenario: A second round on the same release
- **WHEN** the row runs again on the same release
- **THEN** the row posts no comment

#### Scenario: A changelog without a closing text
- **WHEN** the body of the release names `(#11)` and holds no word `closes`, and the body of pull request 11 holds `Closes #101`
- **THEN** issue 101 gets the comment

#### Scenario: An open issue and a pull request
- **WHEN** the body of a pull request holds `Closes #103` for an open issue and `Closes #104` for a pull request
- **THEN** neither number gets a comment

### Requirement: A marker makes each comment once
The comment `Released in <tag>` SHALL start with the line `<!-- devops roadmap release <tag> released -->`. The row SHALL post none on an issue that holds a comment with that line. The ledger `release_comments.json` beside `schedule.json` SHALL only save requests: a missing ledger reads as empty, and one that exists and cannot be read SHALL fail the row and name the file.

#### Scenario: The ledger is lost
- **WHEN** the comments exist, the ledger file does not, and the row runs
- **THEN** the row reads the comments of each issue, posts none, and writes the ledger

#### Scenario: A release that the ledger holds as done
- **WHEN** the ledger holds both flags of a release as done
- **THEN** the round sends the request for the list of releases and no request for that release

#### Scenario: A ledger that cannot be read
- **WHEN** the ledger file holds text that is not JSON
- **THEN** the row fails and the message names the file

### Requirement: The row takes the releases of the last 12 hours
The row SHALL read the 30 newest releases and take those that are published within 12 hours of the round and are neither a draft nor a prerelease. A release outside that window SHALL get no comment, and the ledger SHALL drop its entry.

#### Scenario: Old, draft and prerelease
- **WHEN** the list holds a release of 13 hours ago, a draft and a prerelease
- **THEN** the row reads no pull request for them and posts no comment

### Requirement: Live since waits for both digests
The row SHALL post `Live since <time>` on an issue of a release only when Deployment `roadmap-service` runs the digest that the tag of the release names for the `service` image and CronJob `devops-cli-runner` runs the digest for the `runner` image. The time is the time of the round in UTC to the minute. The comment SHALL start with the line `<!-- devops roadmap release <tag> live -->`, and the row SHALL post it once.

#### Scenario: Only the Service image has rolled
- **WHEN** the Deployment runs the digest of the release and the CronJob runs an older one
- **THEN** the row posts no `Live since` comment

#### Scenario: Both images have rolled
- **WHEN** both digests are the digests of the release
- **THEN** each closed issue of the release holds exactly one `Live since` comment with the time of the round

#### Scenario: A second round
- **WHEN** the row runs again after the comments
- **THEN** the row posts no comment

### Requirement: A newer release that runs makes an older release live
When the cluster runs the digests of a release of the list, the row SHALL treat that release and every older release of the list as live, and SHALL post the same time on their issues. A release newer than the one that runs SHALL get no `Live since` comment.

#### Scenario: Two releases and the newer one runs
- **WHEN** releases `v1.0.0` and `v1.1.0` are in the window and the cluster runs the digests of `v1.1.0`
- **THEN** the issues of both releases each hold one `Live since` comment

#### Scenario: Two releases and the older one runs
- **WHEN** the cluster runs the digests of `v1.0.0`
- **THEN** only the issues of `v1.0.0` get `Live since`

### Requirement: A failed read stops no comment of the round
A failed read of the cluster or of the registry SHALL post no `Live since` comment and SHALL NOT stop the `Released in` comments of the round. After both passes the row SHALL fail once and name each release that it could not check.

#### Scenario: The cluster does not answer
- **WHEN** the read of the Deployment raises `ClusterJobError`
- **THEN** the `Released in` comments are posted, no `Live since` comment is posted, and the row fails and names the release

### Requirement: The row writes no release, tag or file
The row SHALL send only reads and issue comments to GitHub. It SHALL write no release, tag, branch, label or file of the repository, and it SHALL need no clone.

#### Scenario: The requests of a round
- **WHEN** a test records the requests of a round that posts both comments
- **THEN** each request is a GET or a POST to the comments of an issue, and the row has `needs_clone` false

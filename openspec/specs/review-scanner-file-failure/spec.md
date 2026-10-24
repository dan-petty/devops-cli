# review-scanner-file-failure Specification

## Purpose
How a review records static scanner execution outcomes per file. A failure on one file does not mark the whole tool as failed when other files succeed. The coverage matrix records the failure on the row of the file, and the tool reports how many files failed. In addition, files deleted in a branch or pull request do not reach review pages.

## Requirements

### Requirement: Deleted files do not reach review pages or targets
A review of a branch or pull request SHALL exclude deleted files from review pages and review targets.

#### Scenario: A branch deletes a YAML file
- **WHEN** a review runs on a branch that deletes a YAML file
- **THEN** the deleted file is not included in the review pages
- **AND** the deleted file is not included in the review targets

### Requirement: A failed manifest does not mark the whole tool as failed
When a static scanner scans multiple files and one file fails while another succeeds, the tool status SHALL read `ran; N of M files failed`.

#### Scenario: A review scans two manifests and one fails
- **WHEN** Kube-linter scans two manifests and one manifest fails with an error while the other succeeds
- **THEN** the findings from the successful manifest are admitted
- **AND** the coverage matrix marks the failed manifest as `failed(<reason>)`
- **AND** the coverage matrix marks the successful manifest as `scanned`
- **AND** the Static Analyzers table reports `ran; 1 of 2 files failed: <reason>`

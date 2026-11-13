# pr-squash-diff Specification

## Purpose
Which changes of a pull request `devops review pr` and `devops ai analyze pr` read: the files and the diff that the squash merge applies, which is the compare of the tip of the base branch and the head commit, and not the stale base of the pull request payload.

## Requirements

### Requirement: A PR review reads the diff that the squash merge applies
The command `devops review pr` SHALL read the files and the diff of a pull request from the compare of the tip of its base branch and its head commit, and SHALL read the base text and the base conventions at the merge base of that compare. It MUST NOT read the pulls files endpoint or the diff of the pulls endpoint, and MUST NOT read a file at the `base.sha` of the pull request payload.

#### Scenario: A moved merge base
- **WHEN** a merge of the base branch into the pull request moved its merge base, the payload's `base.sha` and the pulls files and diff endpoints still name the old base, and the compare of the base branch and the head commit names another merge base
- **THEN** the review pages hold only the files of the compare, the base text and the conventions are read at the merge base of the compare, and no request names `base.sha` or the pulls files path

#### Scenario: The base worktree
- **WHEN** the fetch of the pull request head into the local checkout succeeds
- **THEN** the base worktree of the review is at the merge base of the compare

#### Scenario: A diff that names no reviewable file
- **WHEN** the diff names no reviewable file and the review posts its comment
- **THEN** the comment lists the files of the compare that the review read, less the deleted files, and the command reads the file list only one time

### Requirement: A PR review refuses a compare at the file limit
The command `devops review pr` SHALL end with status 1 when the compare of the base branch and the head commit lists GitHub's limit of files for one comparison, with a message that names the limit and `devops review branch`, and SHALL read no diff.

#### Scenario: The compare lists 300 files
- **WHEN** the compare of the base branch and the head commit lists 300 files
- **THEN** the command exits 1, its message names 300 files and `devops review branch`, and it makes no diff request

### Requirement: The PR analysis reads the files of the compare of its base branch
The command `devops ai analyze pr` SHALL read the files of a pull request from the compare of the tip of its base branch and its head commit, and MUST NOT read the pulls files endpoint. A compare that lists GitHub's limit of files SHALL give an analysis of the listed files and a warning that names the limit.

#### Scenario: A moved merge base
- **WHEN** the pulls files endpoint lists a file that the compare of the base branch and the head commit does not list
- **THEN** the analysis holds only the files of the compare, and the command reads only the pull request and the compare

#### Scenario: The compare lists 300 files
- **WHEN** the compare of the base branch and the head commit lists 300 files
- **THEN** the command exits 0, the analysis holds the 300 files, and a warning names the limit of 300 files

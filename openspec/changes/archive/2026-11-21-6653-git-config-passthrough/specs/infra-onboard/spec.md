## MODIFIED Requirements

### Requirement: The report reads the default branch at origin
The command SHALL read the infra repo at the head of its default branch at `origin`, never in its working tree. It SHALL fetch `origin` with no prompt and no credential `-c` value: git gets the credential from its configured helper, `gh auth git-credential` in the devcontainer and the images. It SHALL export the tracked files of the commit that `refs/remotes/origin/HEAD` names into a new private folder, read the repo there, and remove it. It MUST NOT change a file or a branch of the checkout.

#### Scenario: The checkout is on an old branch
- **WHEN** the checkout is on the branch `feat/old`, which has no collections file and no CI workflow, and `origin/main` holds both
- **THEN** each of the 17 rows is `present`, and the Ansible commands ran in a folder outside the checkout that no longer exists

#### Scenario: No default branch is recorded
- **WHEN** the checkout has no `refs/remotes/origin/HEAD` after the fetch
- **THEN** the command exits 1 with the error code `INFRA_READ_FAILED`, names the step `git -C <checkout> remote set-head origin --auto`, and starts no Ansible command

#### Scenario: The fetch fails
- **WHEN** `git fetch` exits 128 with a token in its error text
- **THEN** the command exits 1 with the error code `INFRA_READ_FAILED`, names `git fetch --quiet origin` and git's reason with the token masked, and starts no other command

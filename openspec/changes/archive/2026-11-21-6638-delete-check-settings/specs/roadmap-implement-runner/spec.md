## MODIFIED Requirements

### Requirement: A network git call of the implement job reads no file that the agent can write
The implement job SHALL run each git call that reaches `origin`, also the calls of `add_worktree`, through `OriginGit`: in a new bare git folder whose `objects` folder links the object folder of the clone, with `CONST_GIT_TOKEN_CALL_CONFIG`, `CONST_GIT_ISOLATED_CONFIG_ENV`, an empty home folder, and the URL of `origin` that the job read before its first item. It SHALL end every leftover process before it makes the folder and again just before the call.

#### Scenario: The options and the environment of the call
- **WHEN** the job fetches a branch
- **THEN** the fetch gets `-c credential.helper=`, `-c credential.https://github.com.helper=`, `-c 'credential.https://github.com.helper=!gh auth git-credential'` and `-c core.hooksPath=/dev/null`, `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`, and a `HOME` that is gone after the call

#### Scenario: A push sends a commit
- **WHEN** the job pushes the commit `<sha>` to its branch
- **THEN** the push gets `--no-verify` and the refspec `<sha>:refs/heads/<branch>`, runs outside the clone, and the remote-tracking ref of the branch in the clone is `<sha>` after it

#### Scenario: Programs that the home folder of the Job names
- **WHEN** a turn of the agent writes into the git configuration of the home folder a hook folder with a `pre-commit`, `post-commit`, `pre-push` and `reference-transaction` hook and a credential helper, each of which writes the `GH_TOKEN` that it sees, and the job runs a Planned item to its pull request
- **THEN** the branch of the item is on `origin`, the `pre-commit` hook ran with no token, and no program wrote the session's token

#### Scenario: A server that asks for credentials
- **WHEN** a credential helper is in the home folder and in the configuration of the clone, an `http.proxy` with `http.sslVerify=false` is in both, and the job pushes to a loopback server that answers 401 with a Basic challenge
- **THEN** no helper runs, no request reaches the proxy, the server receives no `Authorization` header, and the push fails

#### Scenario: A pre-push hook of the clone
- **WHEN** the configuration of the clone sets `core.hooksPath` to a folder with a `pre-push` hook, and the job pushes to a bare repository on disk
- **THEN** the branch is on the bare repository, and the hook did not run

#### Scenario: A pre-push hook in the hooks folder of the clone
- **WHEN** the hooks folder of the clone holds a `pre-push` hook, no `core.hooksPath` is set, and the job pushes to a bare repository on disk
- **THEN** the branch is on the bare repository, and the hook did not run

#### Scenario: A URL that the home folder or the clone names
- **WHEN** the home folder and the configuration of the clone hold an `insteadOf`, a `pushInsteadOf` or a `pushurl` that names a loopback server that asks for credentials, and the job pushes to a bare repository on disk
- **THEN** the branch is on the bare repository, and the server receives no request

### Requirement: The leftover processes end before each part of a network git call
`OriginGit` SHALL end every leftover process before it makes the new folder, and again just before the call with the token.

#### Scenario: The order of the calls
- **WHEN** the job fetches a branch
- **THEN** the leftover processes end before the new folder is made, again after the refs are copied, and only then the fetch with the token runs

#### Scenario: A refused setting before the call
- **WHEN** the `shallow` file of the clone is a link, and the job fetches a branch in a runner
- **THEN** the leftover processes end first, the call raises `GitSettingsError` that names `shallow`, and the fetch with the token does not run

### Requirement: A refused setting at a checkpoint or stop push stops the item at once
A `shallow` file of the clone that is a link, or is not a regular file, at the push of a checkpoint SHALL stop the item with the class `git_config` at once, before the job writes a record of the push. Such a file at the push of a stop SHALL give the stop the class `git_config`.

#### Scenario: A setting before a checkpoint push
- **WHEN** the agent makes the `shallow` file of the clone a link in group 1 of a change of four groups, and group 1 passes
- **THEN** the checkpoint before group 2 stops the item with the class `git_config`, and the job asks the model for nothing more

#### Scenario: A setting that an exit check writes
- **WHEN** an exit check of the step makes the `shallow` file of the clone a link and fails, and no repair round is left
- **THEN** the item stops with the class `git_config`, and the comment names `shallow`

## REMOVED Requirements

### Requirement: A git setting that the job does not allow stops the item
**Reason**: The scan protects no call with the token. `OriginGit` runs each fetch and push in a new git folder with `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`, so git reads none of the scanned settings (#6638). The scan ran `git ls-files` and `git check-attr` in the checkout, so a `core.fsmonitor` program ran before the scan refused it, and it refused blobless clones, Git LFS repositories and the `--shared` evaluation clone.
**Migration**: The requirement "A network git call of the implement job reads no file that the agent can write" keeps the token away from each setting that the agent can write. The two-container Job of #3700 removes `OriginGit`.

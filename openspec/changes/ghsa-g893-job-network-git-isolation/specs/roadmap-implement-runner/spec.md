## ADDED Requirements

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

#### Scenario: The order of the calls
- **WHEN** the job fetches a branch
- **THEN** the leftover processes end before the new folder is made, again after the refs are copied, and only then the fetch with the token runs

### Requirement: A git setting that the job does not allow stops the item
In a runner, the implement job SHALL check the git settings of the checkout when each turn of the agent ends and before each network git call (`check_settings`). A setting that the job does not allow SHALL stop the item with the failure class `git_config` and push nothing. The reason and the log line SHALL name each key, or each attribute with its path, and SHALL hold no value.

#### Scenario: What the job does not allow
- **WHEN** the checkout holds a key of the scope `local` or `worktree` outside `CONST_GIT_ALLOWED_SETTINGS` and its patterns, an attribute `filter` with a value, an attribute `diff` that is no built-in pattern of git, an attribute `merge` other than `text`, `binary` and `union`, or the file `objects/info/alternates` of the clone
- **THEN** `refused_settings` names it

#### Scenario: A filter
- **WHEN** a turn of the agent writes `filter.x.clean` into the configuration of the clone and `* filter=x` into `.gitattributes`
- **THEN** the item stops with the class `git_config`, the job runs no `git add`, `git commit`, `git push` or `git fetch` after the turn, and the comment names `filter.x.clean` and the attribute `filter` of `.gitattributes`, and holds no value of either

#### Scenario: A GPG program
- **WHEN** a turn of the agent writes `gpg.program` and `commit.gpgsign` into the configuration of the clone
- **THEN** the item stops with the class `git_config`, and the comment names `gpg.program` and holds no value

#### Scenario: A credential helper
- **WHEN** a turn of the agent adds `credential.helper` to the configuration of the clone
- **THEN** the item stops with the class `git_config`, and the comment names `credential.helper` and holds no value

#### Scenario: The settings of a new clone
- **WHEN** the job runs an item in a clone that `git clone` made, with the identity that `ensure_checkout` sets
- **THEN** the check refuses no key

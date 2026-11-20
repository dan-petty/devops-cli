## MODIFIED Requirements

### Requirement: A reclaim keeps a worktree that it does not manage
`devops repos worktrees add` SHALL keep a worktree that is outside the agent worktrees directory, also when its directory is missing, and a worktree under it that holds ignored data files, as the scope rule of `devops repos worktrees prune` defines them. It SHALL read no pull request for such a worktree, SHALL take the rule from the function that prune uses, and SHALL name each worktree that its scope check keeps, with the reason, in the output and in the `kept` list of the JSON report.

#### Scenario: A merged worktree outside the directory stays
- **WHEN** a clean, unlocked worktree outside the agent worktrees directory has a tip that is the head of a merged pull request, and the user runs `add 2345 --type feat --slug next`
- **THEN** the directory of that worktree still exists and GitHub receives no request for it
- **AND** the output names it with a reason that names the managed folder, and `w-2345` is created

#### Scenario: A record with a missing directory outside the directory stays
- **WHEN** a worktree outside the agent worktrees directory has a missing directory, and the user runs `add 2345 --type feat --slug next`
- **THEN** `git worktree list` still lists the record and GitHub receives no request
- **AND** the output names it with a reason that names the managed folder

#### Scenario: A worktree with an ignored file stays
- **WHEN** a worktree under the agent worktrees directory has a tip that is the head of a merged pull request, and it holds `.data/agent/scratch/note.md`, which `.gitignore` hides
- **THEN** the worktree and the note still exist
- **AND** the output names the worktree with the reason `holds 1 ignored data file`

#### Scenario: A worktree with a local environment file stays
- **WHEN** a worktree under the agent worktrees directory has a tip that is the head of a merged pull request, and it holds `.env.local`, which `.gitignore` hides
- **THEN** the worktree and the file still exist

#### Scenario: A data file written after the check stays
- **WHEN** a clean worktree under the agent worktrees directory at a merged head holds no data file when the reclaim checks it, and an agent writes `.data/agent/scratch/note.md` in it while the reclaim reads GitHub
- **THEN** the worktree and the note still exist, because prune asks the rule again right before each removal, and `w-2345` is created
- **AND** the reclaim does not list the worktree in `kept`, as it lists no other refusal of prune

#### Scenario: A worktree with only caches is removed
- **WHEN** a clean worktree under the agent worktrees directory has a tip that is the head of a merged pull request, and its only ignored files are `.venv/x`, `src/pkg/__pycache__/m.pyc` and `.pytest_cache/v`, or only `.data/cache/x`
- **THEN** the reclaim removes the worktree and names it with its size

#### Scenario: The prune command keeps its scope
- **WHEN** a clean worktree outside the agent worktrees directory has a tip that is the head of a merged pull request, and the user runs `devops repos worktrees prune --confirm`
- **THEN** the worktree and its directory still exist, and the command names it with the reason that the reclaim gives

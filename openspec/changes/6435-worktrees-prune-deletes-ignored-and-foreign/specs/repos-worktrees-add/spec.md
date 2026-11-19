## MODIFIED Requirements

### Requirement: A reclaim keeps a worktree that it does not manage
`devops repos worktrees add` SHALL keep a worktree that is outside the agent worktrees directory, also when its directory is missing, and SHALL read no pull request for it. It SHALL keep a worktree under the directory that holds a file which `.gitignore` hides. It SHALL name each worktree that it keeps for one of these reasons, with the reason and the managed folder, in the output and in the `kept` list of the JSON report.

#### Scenario: A merged worktree outside the directory stays
- **WHEN** a clean, unlocked worktree outside the agent worktrees directory has a tip that is the head of a merged pull request, and the user runs `add 2345 --type feat --slug next`
- **THEN** the directory of that worktree still exists and GitHub receives no request for it, and the output names it with a reason that names the managed folder, and `w-2345` is created

#### Scenario: A record with a missing directory outside the directory stays
- **WHEN** a worktree outside the agent worktrees directory has a missing directory, and the user runs `add 2345 --type feat --slug next`
- **THEN** `git worktree list` still lists the record, GitHub receives no request, and the output names it with a reason that names the managed folder

#### Scenario: A worktree with an ignored file stays
- **WHEN** a worktree under the agent worktrees directory has a tip that is the head of a merged pull request, and its only change is a file that `.gitignore` hides
- **THEN** the worktree and the ignored file still exist, and the output names the worktree with a reason that gives the number of ignored paths

#### Scenario: The prune command applies the same scope
- **WHEN** a clean worktree outside the agent worktrees directory has a tip that is the head of a merged pull request, and the user runs `devops repos worktrees prune --confirm`
- **THEN** the worktree and its directory still exist, and the command names it with the same reason that the reclaim gives

#### Scenario: The prune command keeps its scope
- **WHEN** a clean worktree outside the agent worktrees directory has a tip that is the head of a merged pull request, and the user runs `devops repos worktrees prune --confirm`
- **THEN** the command removes that worktree

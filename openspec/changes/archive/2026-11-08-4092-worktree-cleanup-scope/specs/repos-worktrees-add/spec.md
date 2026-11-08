## MODIFIED Requirements

### Requirement: A run reclaims the worktrees of merged work first
`devops repos worktrees add` SHALL remove each worktree that `devops repos worktrees prune --confirm` removes and that is under the agent worktrees directory, before it checks who holds the issue, and SHALL name each removed worktree with the size of its directory. The JSON report SHALL list them in `reclaimed`. The command SHALL keep a worktree that is outside the agent worktrees directory, also when its directory is missing, SHALL read no pull request for it, and SHALL keep a worktree under the directory that holds a file which `.gitignore` hides. It SHALL name each worktree that it keeps for one of these two reasons, with the reason, in the output and in the `kept` list of the JSON report. A worktree that a run in parallel already removed is not a failed reclaim: the run SHALL report it as removed and say nothing of a failed reclaim. `--no-reclaim` SHALL skip the step and read no pull request.

#### Scenario: A merged worktree is removed
- **WHEN** a clean, unlocked worktree under the agent worktrees directory has a tip that is the head of a merged pull request, and the user runs `add 2345 --type feat --slug next`
- **THEN** the directory of that worktree no longer exists and the output names it with its size
- **AND** the worktree `w-2345` is created

#### Scenario: A merged worktree no longer holds its issue
- **WHEN** the merged worktree is under the agent worktrees directory and has the branch `chore/2344-old`, and the user runs `add 2344 --type chore --slug again`
- **THEN** the old worktree is removed and `w-2344` is created

#### Scenario: Other worktrees stay
- **WHEN** a worktree is dirty, locked, or has a tip that no merged pull request heads
- **THEN** `add` keeps it

#### Scenario: A merged worktree outside the directory stays
- **WHEN** a clean, unlocked worktree outside the agent worktrees directory has a tip that is the head of a merged pull request, and the user runs `add 2345 --type feat --slug next`
- **THEN** the directory of that worktree still exists and GitHub receives no request for it
- **AND** the output names it with the reason `outside the managed folder`, and `w-2345` is created

#### Scenario: A record with a missing directory outside the directory stays
- **WHEN** a worktree outside the agent worktrees directory has a missing directory, and the user runs `add 2345 --type feat --slug next`
- **THEN** `git worktree list` still lists the record and GitHub receives no request
- **AND** the output names it with the reason `outside the managed folder`

#### Scenario: A record with a missing directory inside the directory is removed
- **WHEN** a worktree under the agent worktrees directory has a missing directory, and the user runs `add 2345 --type feat --slug next`
- **THEN** `git worktree list` no longer lists the record and GitHub receives no request

#### Scenario: A worktree with an ignored file stays
- **WHEN** a worktree under the agent worktrees directory has a tip that is the head of a merged pull request, and its only change is a file that `.gitignore` hides
- **THEN** the worktree and the ignored file still exist
- **AND** the output names the worktree with a reason that says the file is ignored

#### Scenario: Reclaim skipped
- **WHEN** the user runs `add 2344 --type chore --slug again --no-reclaim` and the merged worktree of issue 2344 exists
- **THEN** the command exits 1 and names that worktree as the holder
- **AND** GitHub receives no request

#### Scenario: A run in parallel removes a worktree first
- **WHEN** a run in parallel removes a merged worktree before `add` removes it, so `git worktree remove` of it fails
- **THEN** `add` reports the worktree as removed, creates the new worktree, and says nothing of a failed reclaim

#### Scenario: The prune command keeps its scope
- **WHEN** a clean worktree outside the agent worktrees directory has a tip that is the head of a merged pull request, and the user runs `devops repos worktrees prune --confirm`
- **THEN** the command removes that worktree

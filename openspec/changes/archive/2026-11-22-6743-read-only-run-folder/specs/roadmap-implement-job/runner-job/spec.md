## MODIFIED Requirements

### Requirement: A runner Job writes the disk use of its home volume
In a runner Job, the end of each step of the agent and each stop of the job SHALL write one line to the Job log with the step, the bytes on the disk of the worktree and the home, and their 8 largest folders, largest first. The line SHALL read `du -x -B1 -d 1 <worktree> <home>` and SHALL name a folder of the worktree as `worktree/<name>`. Outside a runner Job, the job SHALL read no disk use.

#### Scenario: The end of a step in a runner Job
- **WHEN** a step ends in a runner Job, and du reports the worktree with `.data`, `.venv`, `mutants`, `src`, `tests` and `docs`, and home with `.cache`, `.data` and `.config`
- **THEN** the Job log holds one line with the total of the two arguments and the 8 largest folders, and `.config` is not in it

#### Scenario: A stop of the job
- **WHEN** group 2 of an item stops in a runner Job
- **THEN** the last disk use line of the Job log names the step `group 2`

#### Scenario: Outside a runner Job
- **WHEN** a step ends and `roadmap.implement.in_runner` is false
- **THEN** no `du` command starts and the log holds no disk use line

## ADDED Requirements

### Requirement: A run counts the stray files that the step removed
A run of the eval SHALL pass the stray files that the step deleted to `diff_scope` and `no_scratch`. The diff holds none of them, but the agent wrote them. `diff_scope` SHALL fail on each as a path outside the group, and `no_scratch` SHALL fail on each that looks like a scratch file.

#### Scenario: A step that removes a scratch file
- **WHEN** the model writes `scratch.py` in the root with the files of the group, and the step ends done
- **THEN** the tree and the diff hold no `scratch.py`, and `diff_scope` and `no_scratch` fail and name it

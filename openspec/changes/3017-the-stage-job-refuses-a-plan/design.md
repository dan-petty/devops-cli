# Design

## Decisions

- **Find the creating group with a map from each created path and its parent folders to the first group that lists it in `creates`.**: `path_problems` already walks the groups in order and accumulates `created`. A map built in the same walk gives the group number without a second pass over the groups.
- **Name the first later group that creates the path, and tell the model to move it before the reading group.**: The issue asks that the problem name both groups. The first creating group is the one the model must move, and a later duplicate would only confuse the reply.
- **Keep the current message for a path that no group creates.**: The hint about the files with the same name still applies there, and no creating group exists to name.
- **Add the new cases to `tests/roadmap/test_roadmap_stage_paths.py`.**: The tests of `path_problems` already live there, and a second file would split the tests of one function.

## Rejected alternatives

- **Create a new test file for group-ordering checks.**: `tests/roadmap/test_roadmap_stage_paths.py` already holds the tests of `path_problems`, including `test_a_path_that_a_later_group_creates_is_missing_in_the_earlier_group` at line 92, so a new file would split one function's tests.
- **Report the missing path only against the reading group and leave the message as it is.**: The issue's acceptance criterion asks for a problem text that names both groups, and the existing test at line 99 asserts only `group 1`.
- **Name every later group that creates the path.**: `path_problems` reports a path once, at its first place, so one creating group is enough to tell the model what to move.

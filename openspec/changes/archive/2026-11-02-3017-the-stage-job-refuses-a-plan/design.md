# Design

## Decisions

- **Find the creating group with a map from each created path and its parent folders to the first group that lists it in `creates`.**: `_first_creators` builds the map in one pass over the groups. `path_problems` already finds a missing path only when no group up to the reading group creates it, so any group in the map for that path comes later than the reading group.
- **Use a second message for a forward read, and keep the first for a path that no group creates.**: The first message ends "Name a file that exists, or make the group that creates it list it in `creates`" and says "no group up to group {group} creates it". Both are wrong when a later group lists the path. The forward-read message has no same-name hint, because the path is a new file and the hint would say "No file has this name".
- **The final text, in ASD-STE100.**: `stage_problem_path_later` reads: "Group {group} names `{path}` in {place}. The staged commit has no such file, and group {later} creates it after group {group}. Move group {later} before group {group}, or move the work that needs `{path}` into group {later} or a group after it." `stage_problem_path` stays as it is.
- **Name only the first creating group.**: `path_problems` reports a path once, so one group is enough to tell the model what to move.
- **Add the cases to `tests/roadmap/test_roadmap_stage_paths.py`.**: The tests of `path_problems` already live there.
- **The call in `stage.py` after a split needs no change.**: It calls `path_problems` and shares the message.

## Rejected alternatives

- **Create a new test file for group-ordering checks.**: `tests/roadmap/test_roadmap_stage_paths.py` already holds the tests of `path_problems`, so a new file would split the tests of one function.
- **Add a sentence to the existing message and keep its tail.**: The tail asks the model to make a group "list it in `creates`", but the later group already does, so the model gets two contradictory orders. The new test asserts that the tail is absent for a forward read.
- **Name every later group that creates the path.**: A path is reported once, and a later duplicate would only confuse the reply.
- **A test for "a plan whose groups create what they read passes".**: `test_a_path_that_an_earlier_group_creates_passes_in_a_later_group` covers it, and a copy would pass on the base.

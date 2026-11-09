# Design

## Decisions

- **Judge the path of a citation span with the pattern that the citation check already uses.**: `_CITED_PATH` defines a path in `path:line:text` and `path:def name`, so one definition reads the path for both checks.
- **Accept a claim of a file name, or of the end of a path, when a read path ends with it after a `/`.**: A plan writes `constants.py` for `src/devops_cli/config/constants.py`, and the claim is true. A claim of another directory, such as `src/other/constants.py`, is not a suffix of the read path and stays refused.
- **Blank the code spans that are no tool name before the sentence is searched for a verb of reading.**: A quoted line of code is data of the repository, not a claim of the plan. The name of a toolbox tool, such as `read_file`, is kept because it is a call claim.
- **Keep the rule that the first path span of a sentence is the one that the gate judges.**: The change removes false refusals and adds no new refusal.

## Rejected alternatives

- **Add the paths that tool answers show to the trace facts.**: A path in a `search_code` answer is a path that the run saw, not one that it read. The issue #4281 and its change own the changes to the trace facts.
- **Skip the trace gate for a span that holds a colon.**: A claim of an unread file in the form `path:def name` is a false claim, and the gate must refuse it. The golden replay and the new test keep that case.

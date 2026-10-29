# Design

## Labels of the sub-command histogram

`sub_command` holds the command path below `devops` (`pr threads reply`), not the leaf name (`reply`). Leaf names repeat across command groups (`config list`, `pr list`), so a variable of leaf names would put the series of several commands in one panel. `command` holds the first word of that path, which is the same value that `devops_cli_command_total` sends, so the `$command` variable filters both series.

Rejected: a label `command_path` that holds `devops pr threads reply`. The word `devops` is in each value and adds nothing to a panel title.

Rejected: a new histogram for the sub-commands. `devops_cli_subcommand_duration_seconds` already times each sub-command, and no dashboard read it.

## Layout

Rejected: a row that repeats for each `command` with a panel inside that repeats for each `sub_command`. A nested repeat does not scope the inner variable to the row, so each row would hold a panel for every selected sub-command and most panels would be empty. In the v1 schema no rule hides an empty panel.

Rejected: the v2 schema with the Auto grid and a "query has data" rule. The classic file provider refuses a plain v2 dashboard (see the proposal's Feasibility).

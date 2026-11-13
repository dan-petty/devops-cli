# Design

## Decisions

- **The false `when` item decides.** ansible-core writes the first false item of the `when` list into `false_condition`. A skip whose item names `ansible_check_mode` happened because of check mode, so the plan shows it as unchecked. A role puts the condition of the work first in a `when` list, so a skip with nothing to do names no check mode and stays out of the unchecked tasks.
- **Jinja2 reads the names.** The plan parses the item with `jinja2.Environment.parse` and looks for a `Name` node `ansible_check_mode`. A text search would also match a longer name such as `my_ansible_check_mode`. The parse renders and compiles nothing, so the tests and filters of Ansible need not exist.
- **The safe side stays.** A skip with no `false_condition`, a result that does not read as JSON and a `when` item that does not parse stay unchecked.
- **A loop item counts the same way.** In ansible-core 2.22.0, an item that a false `when` skips has `false_condition` but no `skipped` key. The plan reads the item as it reads a task skip.

## Rejected alternatives

- **Change the gVisor role only.** The role could hide the check-mode skip, for example with a failure that `failed_when` ignores in check mode. That swallows an error, and each other role with such a `when` keeps the problem.
- **Show every skip by a false `when` as unchecked.** Then every plan with a normal false `when` needs the level `full`, and the plan no longer shows which skips have nothing to do.
- **`jinja2.meta.find_undeclared_variables`.** It compiles the tree and fails on the tests of Ansible, such as `is changed`.

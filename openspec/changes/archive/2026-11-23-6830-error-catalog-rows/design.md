# Design

## Decisions

- The description is the first paragraph of the cleaned docstring, joined on one line. Reason: a docstring writes its first sentence over several lines, and a paragraph ends at a blank line.
- The domain is the first name below `devops_cli`, and the module name below `devops_cli.exceptions`. Reason: the existing rows already use that name for the error modules, and a top package names the area for the other classes.
- A bar in a description is escaped. Reason: an unescaped bar breaks the table row.

## Rejected alternatives

- A cut of the description at a fixed length. A cut ends a sentence in the middle again.
- The full module path as the domain. It is the defect.

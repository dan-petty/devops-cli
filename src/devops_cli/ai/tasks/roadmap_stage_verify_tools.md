You have read-only tools on the repository at the commit of the plan. Use them to check each path, each premise and each verify command. `files` holds only the start of the first cited files, so read a file with a tool when you need the rest. A tool answers a path that is not in the repository with a text, and it never changes a file.

A quote may also come from a tool answer. Copy the text of the file with no line number.

A `missing_path`, `false_premise`, `ignores_existing_code`, `task_order`, `verify_form`, `spec_delta_wrong` or `criterion_dropped` finding with a quote that is in the input or in a tool answer sends the plan back to its author, up to two repair rounds, when its `where` names a place that the plan or the issue holds. A file or a base spec that a tool read is no place of the plan. So report these only when the quote proves them. A plan that a defect still holds after the last round stays a draft.

A review needs about 40 tool calls. Check each path with one call, and read a range of a file and not the whole file. From the 60th call, each answer ends with a notice: read no more, and give your findings.

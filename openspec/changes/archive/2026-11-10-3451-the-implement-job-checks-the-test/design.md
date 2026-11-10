# Design

## Decisions

- **Read the task text and the collected count in the implement step, not in the plan check.**: The plan holds the task text only and cannot see the delivered test, and the step holds the checkout of the group.
- **Compare the items that a pytest collection reports with the count that the task names.**: pytest reports one item for each parametrized case and one item for a loop over the same cases, so one rule covers both forms.
- **Give a mismatch the class test and the named test file as its repair path.**: FailureClass.TEST selects the repair action, and a repair round re-runs every exit check, so the form is checked again after the turn.
- **Record the check with ImplementTrace.check.**: That event already holds a command and a status, and the trace table is the record that a reviewer reads.
- **Read the count after the phrase parametrized test over as a digit or a number word from one to twenty.**: The archived task states its count that way, and the plan format needs no new field.
- **Check a named parametrized test that states no count for more than one collected item.**: A loop test over the same cases still collects one item, so the check refuses it.
- **Run no form check for a fix step.**: The group of a fix step is generated from the failed check and names no test form of a task.
- **Reuse is_test_file to decide that a code span names a test file.**: It already holds the tests/ prefix, the .py suffix and the test_ name prefix.
- **Add no setting and no new constant.**: The collection run uses the existing roadmap.implement.command_timeout_seconds bound, and a new CONST_ROADMAP_ constant would need an entry in the limit table.
- **Change no prompt and no document.**: A change to the implement prompt needs a score before and after, and the repair turn names the mismatch to the model in the step itself.

## Rejected alternatives

- **Detect a loop test by parsing the test function with ast.**: The staging commit holds no loop test: `tests/output/test_network_table_color.py:23:@pytest.mark.parametrize(`. A parser must also follow every test style, and the collected count already gives one item for a loop.
- **Match the test source with a regular expression.**: Comments and strings make a source match unreliable, and the delivered test is parametrized already.
- **Refuse only a test that is not parametrized.**: That passes the six-versus-eleven mismatch, which is the gap that remains at the staging commit.
- **Add a machine-readable task field for the form and the count.**: That changes the planner output for every task of every change, and the task text already states both.
- **Check the form in the plan check.**: The plan holds the task text only and cannot see the delivered test.
- **Tick the task and report the mismatch in the pull request comment.**: The job would report a success that it did not check, which is the defect of #3451.

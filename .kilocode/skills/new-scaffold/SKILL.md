---
name: new-scaffold
description: Write the files of a new devops command or a new test in project form. Use when you add a command to a group, or when you add a test file for a module of src/devops_cli.
---

# Scaffold a command or a test

Do not write these files by hand. The scaffold knows where each rule puts them.

## Add a command to a group that exists

1. Run `uv run devops new command <group> <command> --dry-run` to see the files.
2. Run `uv run devops new command <group> <command>`.
3. Do the steps that the command prints. They stay manual.

The command adds the function to `src/devops_cli/commands/<group>.py`, the help and message entries to `src/devops_cli/lang/en/`, and a failing test to `tests/commands/`. It writes over no file. A new group is a decision for a person: add the group module and its language classes by hand.

## Add a test for a module

1. Run `uv run devops new test src/devops_cli/<package>/<module>.py`.
2. Replace the failing test with the behaviour you build.

The test sits at the mirror path `tests/<package>/test_<module>.py` and asks for the shared fake of each edge that the module reaches. The rules are in [docs/TESTING.md](../../../docs/TESTING.md).

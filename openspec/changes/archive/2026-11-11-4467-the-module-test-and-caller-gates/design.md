# Design

## Decisions

- **A test of a module imports it.**: `ast` and `build_import_graph` read the imports of each candidate test, at any depth of the test and outside `if TYPE_CHECKING:`. A string, a comment and a path are no import, so `tests/commands/test_new.py` is no test of the messages module. The project already maps changed sources to tests with the same graph in `src/devops_cli/core/test_selection.py`.
- **A package that imports the module stands for it.**: `from devops_cli.lang import MESSAGES` binds the object of `src/devops_cli/lang/en/messages.py`, because `devops_cli.lang` imports `devops_cli.lang.en`, which imports the messages. The record follows the `__init__.py` of each package above the module, nearest first.
- **A test of another changed module that imports the module counts too.**: a group that changes `follow.py` and the messages that `follow.py` shows tests both with the test of `follow.py`. Over the stored replies, the rules of this change clear 14 of the 16 problems of the messages module; the 2 groups left name only tests that they create. The rule reads the plan, not one group, because the record is one map for the plan.
- **`git grep -F -w` finds the candidates, and `ast` decides.**: every import form of `a.b.c` holds the words `a.b` and `c`, so the record searches those two words and parses only the files that hold both. A full parse of the 1,106 test modules takes about 13 s; the candidates of a module are tens of files.
- **`grep_at` searches a fixed string.**: its contract is the files that hold a name, and each caller gives a literal: a metric name, a manifest file name, a dotted module name or a negative-search literal.
- **The recheck tree reads files at its revision.**: `StagedTree` takes a `reader`; the recheck passes one that shows each file at the revision once. A tree with no checkout and no reader records no module test, as the replay tree records no caller.
- **A caller clause names a parameter.**: `changed_functions` reads a clause `add ... to` followed by one or more names, and only when the added part says parameter, argument or keyword. A clause ends at `.`, `:` or `;` outside a code span. A field, a member, a property and a method of a class are no parameter.
- **A call is an `ast` call of the name.**: `calling_files` counts `name(...)` and `value.name(...)`. When no file defines a function or a method of that name, the name is a class or an enum, and it has no caller.

## Rejected alternatives

- **Keep the text search and add `-F` only.**: the fixed search still lists a test that holds the dotted name in a string, and it misses `from devops_cli.lang import MESSAGES`, so the messages module keeps one test, which the refused groups do not name.
- **Count only the direct importers of the module.**: the messages module has one direct importer, `tests/roadmap/implement/test_roadmap_implement_amend.py`, so each plan that adds a message would have to name that unrelated test.
- **Count each test that imports the module at any distance.**: almost every test reaches the messages module, and a group that changes `stage_paths.py` would pass with any stage test, which is the defect that #3414 refuses.
- **Exempt the modules under `src/devops_cli/lang/`.**: a rule for one folder hides the cause, and a test that does import the messages is a real test of them.
- **Parse every test module once for the job.**: about 13 s for each staged commit, against tens of files for each changed module.
- **Keep the stem rule of the test naming convention.**: `tests/cloudflare/test_client.py` carries the stem of every `client.py`, and a test that imports no part of a module cannot run it.
- **Require the callers that pass the new parameter only.**: #3307 rejected it, because a default parameter still leaves the call to review.

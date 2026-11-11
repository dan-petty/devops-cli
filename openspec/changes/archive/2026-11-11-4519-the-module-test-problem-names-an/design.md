# Design

## Decisions
- The order lives in `record_module_tests`. One function orders the tests, and every reader of the record sees the nearest test first.
- `_importing_tests` returns each test with the exporter names that it imports. A test that imports the dotted name of the module is a direct importer. No second search and no second parse run.
- The mirror path is `tests/<folders after src/devops_cli/>/test_<module>.py`. A module at the top of the package has no mirror rank, as the project names no mirror for it.
- The sort key is the tuple (not mirror test, not direct importer, not in mirror folder, path). The tests of another changed module, which import it, follow in path order.

## Rejected alternatives
- Rank in `_unnamed_module_test`: it holds no reader and no import graph.
- Add the mirror test when it is not in the record: the record holds tests that import the module, and a test that does not run the module is no test of it.
- A second record of nearest tests: it changes the type for every caller.

"""What test modules share, so none imports the root conftest or another test module (#1312).

`paths` names the repository root and its test data directories, `fakes` holds one fake per
external edge, `waits` holds the bound a test waits with for another thread or process (#1664),
`builders` builds the objects tests make most often, `refused_programs` names the programs no
test starts for real (#1666), and `review_replies`, `telemetry_capture`, `roadmap_board_replies`,
`markdown_examples`, `hung_children` and `session_spawns` hold the test data and helpers more
than one test module reads. A module here is shared code, not a test: no
test module or conftest lives under this package, which the registration enforces.

Every submodule and subpackage here is a pytest plugin; this `__init__.py` is not. The root
conftest's one `pytest_plugins` entry names `bootstrap`, which isolates HOME and then registers
the rest, so a fixture defined in one reaches every test that asks for it, and an autouse one
applies to the whole suite. A module defines no `pytest_*` name that is not a hook, and defines
the fixtures it registers with `pytest.fixture` rather than importing another module's or
handing one out by a module-level `__getattr__`, which the registration enforces. Since every
run imports it, its top level and its class bodies hold only docstrings, imports at the top
level, defs, classes, assignments to names alone and `if TYPE_CHECKING:` blocks with no `else`,
which an invariant enforces; the values bound to names, decorators, default arguments, base
classes and metaclasses still run on import unchecked. `bootstrap` imports nothing from
devops-cli at its top. A change to a module that defines a fixture or hook, or that such a
module or a conftest imports, runs the whole suite; a change to any other runs the test modules
that import it. A module imports from a support module with `from tests.support[.x] import ...`,
and no module but `bootstrap` holds this package or a package under it, so none reads a
support module it does not import.
"""

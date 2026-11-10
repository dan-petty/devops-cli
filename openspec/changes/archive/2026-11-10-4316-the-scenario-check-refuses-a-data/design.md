# Design

## Decisions

- **Judge a path of the `when` only when a behavior group changes, creates or reads it.**: A group that touches the path builds or uses it as code, and its test must name it. A path that no group touches is data of the scenario.
- **Judge every code identifier of the `when`.**: A function or a class in a condition is code under test, as before.
- **Judge every path and identifier of the `then`.**: The `then` states the behavior under test.
- **Keep the rule that one named span satisfies the scenario.**: The scenario then keeps its present reading, and only the set of spans changes.

## Rejected alternatives

- **Skip every path of the `when`.**: A scenario "`src/x.py` holds a bad line" would need no test of `src/x.py`, and the gate would lose the defects it catches.
- **Skip a scenario that names a data file anywhere.**: A `then` that names code with no test must stay refused.

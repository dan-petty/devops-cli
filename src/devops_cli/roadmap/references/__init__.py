"""The reference step of the alternatives check (#4672): after the verdict of an item, it searches
public code for reference implementations and official documentation, and links what it verified.

- `queries` builds the queries of an item from its body and from the reply of the check.
- `providers` holds the search providers as data: the two GitHub searches and one optional
  provider on an MCP server.
- `candidates` holds the gates and the rank of a candidate repository.
- `relevance` is the decision point `brain.reference_relevance`, which runs in shadow.
- `step` runs the step of one item in its bounds, and gives the verified links.
"""

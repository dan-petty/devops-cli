# Design

## Decisions

- **Keep the second definition.**: Its docstring names why the compare endpoint is used and not the pulls endpoint. The change adds the first caller (#5346) to it, so no fact of the first docstring is lost.
- **Carry no spec delta.**: The method body does not change, so no consumer observes the change.

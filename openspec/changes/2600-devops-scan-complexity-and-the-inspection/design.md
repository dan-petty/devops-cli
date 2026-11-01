# Design

## Decisions

- **Keep the McCabe port in core/code_metrics.py as the single source of complexity for the two readers.**: Ruff is a dev dependency, not a runtime dependency. Its JSON output has no structured field for the complexity number. The port is 90 lines of pure Python with no external dependencies, tested to match Ruff's C901 on 12 samples.

## Rejected alternatives

- **Read complexity from Ruff as a subprocess per scan.**: Ruff is not a runtime dependency (pyproject.toml [dependency-groups] dev). Its JSON output embeds the number in a message string. A subprocess per scan adds latency and a binary dependency.
- **Add Ruff as a runtime dependency.**: Adding a Rust binary as a runtime dependency of a CLI tool is a supply-chain and size cost for a metric that 90 lines of pure Python already compute.

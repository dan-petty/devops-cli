# Design

## Decisions
- A total stays only where a sum has a meaning: concurrent calls, requests and power. The sum of GPU utilisation or of memory percent has no meaning, and the old `Average (Mean)` of "GPU Memory Utilization (%)" gave the same value as its `Total (Sum)`, because both divide used by total memory.
- The cooldown and fallback stats keep their breakdown (`api_base` and `exception_status`, the model pair), so a reader sees which deployment or pair had the events.
- The stats use `colorMode: none`. A count of events has no threshold, and the default thresholds of Grafana would color a count of 80 red.
- The "Qdrant Collections" stat (height 3) and "Qdrant Vectors per Collection" (height 5) share the column of the old panel, so no other panel moves.

## Rejected alternatives
- `or vector(0)` on the stats, as the issue proposes: `expression_violations` in `tests/commands/k8s/test_stack_dashboards.py` refuses a constant fallback in `llm-stack.json`, and `k8s/README.md` says why: a panel with no data must not read as zero. `noValue: "none recorded"` gives the reader the answer with no constant.
- One total stat of all cooldowns (`sum(increase(...[$__range]))`): it hides which deployment cooled down, and the breakdown costs nothing.
- Keeping `Total (Sum)` on "GPU Memory Used": the issue keeps a total only for requests and power, and the sum of the memory of GPUs on different nodes is not a pool that one model can use.

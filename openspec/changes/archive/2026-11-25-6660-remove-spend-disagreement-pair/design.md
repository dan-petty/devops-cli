# Design

## Decisions
- Delete the `spend` entry under `disagreements` in `src/devops_cli/roadmap/project_review/catalog.yaml`.
- Retain `prometheus.cli_spend` and `prometheus.gateway_spend` under `facts` (`section: spend`) so both spend series remain visible independently in project reviews.
- Keep `Disagreement(id="spend", ...)` unit tests in `tests/roadmap/project_review/test_review_facts.py` and `test_review_catalog.py` as synthetic disagreement engine fixtures, while adding shipped-catalog assertions that verify `load_catalog().disagreements` has no `"spend"` entry and `load_catalog().facts` retains both `prometheus.cli_spend` and `prometheus.gateway_spend`.

## Rejected alternatives
- Mint per-client LiteLLM virtual keys and filter `litellm_spend_metric_total` by `api_key_alias`: rejected because Jobs and the CLI share the master key Secret and the streamed-call (`#6165`) and deployment-pricing (`#6002`) discrepancies would still cause the pair to diverge.
- Keep the `spend` disagreement pair with a wider tolerance: rejected because the two metrics count different caller sets and vary in both directions across windows.

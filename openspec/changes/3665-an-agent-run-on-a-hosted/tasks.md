# Tasks

## 1. A hosted group run is priced by the asked model

Kind: behavior. Reads: `src/devops_cli/ai/spend/pricing.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/config/constants.py`. Changes: `src/devops_cli/ai/spend/ledger.py`, `tests/ai/client/test_roadmap_agent_run.py`, `tests/ai/spend/test_ai_spend_ledger.py`.

- [ ] 1.1 Add the tests: a run on each hosted group with replies that name no model, a run on a local group, a reply that names another model, and a chat call with no reply name, all with the gateway host as the cluster host
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 1.2 In `track_request_spend`, take the asked model as `served_model` for a gateway call that has no `served_by`, no `served_model` and a hosted group as model
  - Verification: `$ uv run devops ci test tests/ai/client/test_roadmap_agent_run.py tests/ai/spend/test_ai_spend_ledger.py tests/ai/spend/test_ai_spend_pricing.py`

## Workflow follow-up

- Cache tokens of a run are not passed to genai-prices: #3658.
- The gap between 68 M local prompt tokens on the counter and 27 M at the gateway needs the Service logs: the pull request comment names it for a follow-up issue.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

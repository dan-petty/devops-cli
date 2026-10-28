# llm-slot-wait Specification

## Purpose

The wait of an LLM call for a slot in the process. A call to Ollama waits for a slot on one of its nodes, queued by priority. The wait is a histogram by priority and outcome, and a dashboard panel charts it, so a call that queued in the process is told apart from a slow reply.

## ADDED Requirements

### Requirement: A call to Ollama observes its wait for a slot by priority and outcome
Each call that asks for an Ollama slot SHALL send one observation of the histogram `devops_cli_ai_ollama_slot_wait_seconds`, in seconds, with the label `priority` set to the priority that the call waited with and the label `outcome` set to `ok` when it holds a slot or `timeout` when its deadline passes with no slot.

#### Scenario: A call finds a free slot
- **WHEN** a `high` call asks for a slot on a node with a free slot
- **THEN** one observation is sent with `priority` `high` and `outcome` `ok`

#### Scenario: A call waits for a held slot
- **WHEN** a `normal` call asks for the one slot of a node that another call holds
- **AND** the other call releases the slot while the `normal` call waits
- **THEN** the `normal` call sends one observation with `priority` `normal` and `outcome` `ok`, and a wait above 0 s

#### Scenario: An as-available call finds no free slot
- **WHEN** an `as_available` call asks for the one slot of a node that another call holds
- **THEN** the call fails with an `AIClientError`
- **AND** one observation is sent with `priority` `as_available` and `outcome` `timeout`

### Requirement: The AI spend dashboard charts the p95 Ollama slot wait by priority
`k8s/monitoring/dashboards/ai-spend.json` SHALL have a panel that charts the 0.95 quantile of `devops_cli_ai_ollama_slot_wait_seconds` summed by `priority`, and the count of its observations by `priority`.

#### Scenario: The dashboard queries the slot wait
- **WHEN** a test reads the queries of `ai-spend.json`
- **THEN** one query is the 0.95 `histogram_quantile` of `devops_cli_ai_ollama_slot_wait_seconds` summed by `priority`
- **AND** every query names only series in `INSTRUMENTS`

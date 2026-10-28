## ADDED Requirements

### Requirement: The GPU row shows clock-event reasons, power against the enforced limit and PCIe throughput
The GPU row of `llm-stack.json` SHALL have the panels "GPU Power against Enforced Limit (%)", "GPU Clock Event Reasons (Samples in 5 Minutes)" and "GPU PCIe Throughput". Each panel SHALL select only DCGM families in `tests/fixtures/metrics/dcgm-exporter.yaml` and SHALL have a description.

#### Scenario: The GPU row holds the three panels over captured fields
- **WHEN** the panels between the row "GPUs" and the next row of `llm-stack.json` are read
- **THEN** "GPU Clock Event Reasons (Samples in 5 Minutes)" selects `DCGM_EXP_CLOCK_EVENTS_COUNT` with unit `short`
- **AND** "GPU Power against Enforced Limit (%)" selects `DCGM_FI_DEV_ENFORCED_POWER_LIMIT` and `DCGM_FI_DEV_POWER_USAGE` with unit `percent`
- **AND** "GPU PCIe Throughput" selects `DCGM_FI_PROF_PCIE_RX_BYTES` and `DCGM_FI_PROF_PCIE_TX_BYTES` with unit `Bps`
- **AND** every family that these panels select is in the DCGM capture, and each panel has a description

#### Scenario: The power panel draws the enforced limit on its axis
- **WHEN** the thresholds of "GPU Power against Enforced Limit (%)" are read
- **THEN** it draws a threshold line at 100
- **AND** its `axisSoftMax` reaches that line

#### Scenario: The clock-event panel leaves out an idle GPU
- **WHEN** the query of "GPU Clock Event Reasons (Samples in 5 Minutes)" is read
- **THEN** it groups by `hostname`, `gpu`, `modelName` and `clock_event`
- **AND** it matches `clock_event!="gpu_idle"`

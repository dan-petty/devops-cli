# Spec Delta

## Purpose

The interactive terminal user interface telemetry dashboard provides unified real-time visibility into cluster logs, Prometheus performance metrics, and OpenTelemetry trace waterfalls.

## ADDED Requirements

### Requirement: Embedded LogQL query console with syntax highlighting
The telemetry dashboard panel SHALL provide an embedded LogQL input widget with syntax highlighting that executes LogQL queries against Loki and streams matching log records into the log console.

#### Scenario: An operator executes a LogQL query
- **WHEN** the operator enters a LogQL query into the query bar and submits it
- **THEN** the panel executes the query and streams matching log entries into the log console

### Requirement: Real-time Prometheus performance sparklines and gauges
The telemetry dashboard panel SHALL render ASCII sparklines and progress gauges displaying command execution latencies, LLM token throughput rates, and cache hit ratios.

#### Scenario: Real-time performance metrics display
- **WHEN** telemetry status updates with command latencies, token rates, and cache hit ratios
- **THEN** the panel displays ASCII sparklines for latencies and throughput and an ASCII gauge for cache hit ratio

### Requirement: OpenTelemetry trace waterfall modal
The telemetry dashboard SHALL provide a modal dialog that renders distributed traces and review spans as a hierarchical waterfall tree with relative offset percentages, durations, and latency heatmap bars.

#### Scenario: Operator opens trace waterfall modal
- **WHEN** the operator activates the trace waterfall action on the telemetry panel
- **THEN** the trace waterfall modal opens displaying the span tree, durations, and latency heatmap bars

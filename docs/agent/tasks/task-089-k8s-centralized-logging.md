# Task: Centralized Kubernetes Logging Stack & LogQL Integration (#89)

**Issue**: #89
**PR**: #96
**Status**: Done
**Milestone**: v0.2.15
**Priority**: priority/p0-critical
**Scope**: scope/k8s

## Description
Production-ready centralized logging architecture using Grafana Loki and Fluent Bit with native LogQL parsing, trace correlation, and CLI streaming.

## Deliverables
- [x] Centralized Kubernetes Logging Stack & LogQL Integration (`devops k8s logs`) (P0 - Critical, PR #96 - Merged)
- [x] Declarative Loki and Fluent Bit stack in `k8s/logging/` (`loki-values.yaml`, `fluent-bit-values.yaml`, `networkpolicy.yaml`).
- [x] Registered `logging` stack in `devops k8s deploy-stack --stack logging` and `teardown-stack`.
- [x] Native LogQL parser, pipeline filter evaluator, and query engine in `src/devops_cli/k8s/logql.py`.
- [x] OpenTelemetry `trace_id` extraction and trace correlation in LogQL entries and Grafana Loki datasource.
- [x] Integrated `devops k8s logs [query|tail|stream]` with live follow and fallback to `kubectl logs`.
- [x] Registered FastMCP tools `k8s_logs_query` and `k8s_logs_tail` with 119 schemas exported.
- [x] Unit and integration tests in `tests/test_k8s_logging_stack.py` and `tests/test_k8s_logql.py`.

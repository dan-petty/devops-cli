# Task 803: Disable Third-Party Telemetry Across K8s Stack and DevContainer

**Issue**: [#803](https://github.com/dan-petty/devops-cli/issues/803)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p2-medium`
**Scope**: `type/infra`, `type/security`, `scope/k8s`, `priority/p2-medium`

---

## 1. Description & Objectives

Disables third-party telemetry, phone-home mechanisms, version update checks, and crash reporting across the Kubernetes stack (Grafana, Alloy, Loki, Traefik, Open WebUI, LiteLLM Gateway) and the DevContainer development environment.

Root causes & telemetry vectors addressed:
1. **Grafana & Logging**:
   - Grafana sent anonymous telemetry to `stats.grafana.org`, polled `grafana.com` for application and plugin updates, and pulled news feeds.
   - Grafana Alloy instances (`alloy-metrics`, `alloy-singleton`, `alloy-logs`) sent periodic usage reports to `https://stats.grafana.org/alloy-usage-report`.
   - Grafana Loki reported operational analytics to `https://stats.grafana.org/loki-usage-report`.
2. **Ingress & LLM Services**:
   - Traefik sent anonymous usage telemetry and performed version checks.
   - Open WebUI polled GitHub releases for version updates and lacked explicit opt-outs for Scarf and anonymized telemetry.
   - LiteLLM Gateway lacked explicit telemetry opt-outs in its deployment and ConfigMap.
3. **DevContainer Environment**:
   - VS Code / Antigravity editor lacked explicit telemetry opt-outs for `telemetryLevel`, Red Hat extensions, and workbench experiments.
   - Developer toolchains (Claude Code, Go, Pip, Minikube, NPM, Docker, Hugging Face, Scarf) lacked explicit opt-out environment variables.

### Key Deliverables Completed:
- [x] **Kubernetes Monitoring & Logging Configuration** (`k8s/monitoring/grafana-values.yaml`, `k8s/monitoring/k8s-monitoring-values.yaml`, `k8s/logging/loki-values.yaml`):
  - Added `analytics` and `news` blocks to `grafana.ini` disabling `reporting_enabled`, `check_for_updates`, `check_for_plugin_updates`, `feedback_links_enabled`, and `news_feed_enabled`.
  - Added `selfReporting: enabled: false` and `enableReporting: false` across all Alloy collectors (`alloy-metrics`, `alloy-singleton`, `alloy-logs`).
  - Added `analytics: reporting_enabled: false` to Loki Helm values.
- [x] **Ingress & LLM Stack Configuration** (`k8s/ingress/traefik-values.yaml`, `k8s/llm/values-open-webui.yaml`, `k8s/llm/gateway/configmap.yaml`, `k8s/llm/gateway/deployment.yaml`):
  - Configured `--global.sendanonymoususage=false` and `--global.checknewversion=false` in Traefik values.
  - Injected `ENABLE_VERSION_UPDATE_CHECK: "false"`, `ANONYMIZED_TELEMETRY: "false"`, `DO_NOT_TRACK: "true"`, and `SCARF_NO_ANALYTICS: "true"` into Open WebUI values.
  - Set `telemetry: false` in LiteLLM Gateway ConfigMap and injected `LITELLM_TELEMETRY: "False"` into LiteLLM deployment.
- [x] **DevContainer Environment & Template** (`.devcontainer/devcontainer.json`, `src/devops_cli/templates/devcontainer.json.j2`):
  - Set `telemetry.telemetryLevel: "off"`, `redhat.telemetry.enabled: false`, and `workbench.enableExperiments: false` under editor customizations.
  - Injected environment variables into `containerEnv`: `DO_NOT_TRACK`, `HF_HUB_DISABLE_TELEMETRY`, `SCARF_NO_ANALYTICS`, `NEXT_TELEMETRY_DISABLED`, `CHECKPOINT_DISABLE`, `DOTNET_CLI_TELEMETRY_OPTOUT`, `ANONYMIZED_TELEMETRY`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, `DISABLE_TELEMETRY`, `GOTELEMETRY`, `PIP_DISABLE_PIP_VERSION_CHECK`, `npm_config_update_notifier`, `DOCKER_CLI_HINTS`, `MINIKUBE_WANTUPDATENOTIFICATION`, and `MINIKUBE_WANTREPORTERRORPROMPT`.
- [x] **Agent Instructions & Instruction Generator** (`AGENTS.md`, `src/devops_cli/ai/instruction_generator.py`, `tests/test_instruction_generator.py`):
  - Codified the Mandatory Third-Party Telemetry & Phone-Home Opt-Outs policy into `AGENTS.md` and `instruction_generator.py`.
  - Added requirement for AI agents to disable third-party telemetry and phone-home mechanisms across all tools and configurations when it does not impact functional user experience.
  - Added requirement for AI agents to confirm with the user before disabling web integrations that provide tangible functionality (e.g. plugin/extension update checks, news feeds).
- [x] **Automated Regression Test Suite** (`tests/test_third_party_telemetry.py`, `tests/test_instruction_generator.py`):
  - Authored comprehensive structural assertions verifying zero telemetry across all modified manifests, configs, and devcontainer definitions.
  - Validated 100% pass rate with zero flaky tests.

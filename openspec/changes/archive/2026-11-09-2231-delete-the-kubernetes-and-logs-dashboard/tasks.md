# Tasks

## 1. Source Removal
- [x] 1.1 Remove Kubernetes and Logs tab bindings, panels, and helpers from `src/devops_cli/ui/dashboard.py`
  - Verification: `$ uv run pytest tests/ui/test_ui_dashboard_app.py`
- [x] 1.2 Remove `K8sPanel` and `PodInspector` from `src/devops_cli/ui/widgets.py` and delete `src/devops_cli/ui/pod_inspector.py`
  - Verification: `$ uv run pytest tests/ui/test_ui_widgets.py`
- [x] 1.3 Remove Kubernetes projections and helpers from `src/devops_cli/ui/projections.py`
  - Verification: `$ uv run pytest tests/ui/test_ui_projections.py`
- [x] 1.4 Remove `fetch_k8s_status`, `fetch_pod_events`, and `K8sSummary` from `src/devops_cli/ui/data_providers.py`
  - Verification: `$ uv run pytest tests/ui/test_ui_data_providers.py`
- [x] 1.5 Remove `PodLogSource`, `pod_log_source`, and Kubernetes provider from `src/devops_cli/ui/refresh.py`
  - Verification: `$ uv run pytest tests/ui/test_ui_refresh_coordination.py`
- [x] 1.6 Remove Kubernetes panel from `src/devops_cli/commands/dashboard.py` and default initial tab to `docker`
  - Verification: `$ uv run pytest tests/ui/test_ui_dashboard_cli.py`
- [x] 1.7 Update dashboard constants and tab maps in `src/devops_cli/config/constants.py` and remove unused defaults in `src/devops_cli/config/defaults.py`
  - Verification: `$ uv run pytest tests/test_config_declarations.py`
- [x] 1.8 Update CLI help text for `--tab` in `src/devops_cli/lang/en/help.py`
  - Verification: `$ uv run devops docs check`

## 2. Test and Documentation Updates
- [x] 2.1 Remove obsolete Kubernetes UI tests and update existing dashboard tests
  - Verification: `$ uv run pytest tests/ui/`
- [x] 2.2 Lower swallowed failures ceilings in `tests/fixtures/swallowed_failures_ceilings.json`
  - Verification: `$ uv run python -c "import sys; from tests.gate.swallowed_failures import main; sys.exit(main())"`
- [x] 2.3 Synchronize documentation and verify invariant checks
  - Verification: `$ uv run devops docs check`

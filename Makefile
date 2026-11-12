# Build targets that call an open tool through its own command line. Each target names the files
# it writes; commit them, and never edit them by hand.

# Style Dictionary, from the lock in src/devops_cli/tools_lock/style-dictionary/. The devcontainer
# image puts it on PATH; docs/DESIGN.md gives the install steps for another host.
STYLE_DICTIONARY ?= style-dictionary

# The token build: design/tokens/*.tokens.json to docs/assets/css/tokens-*.css and
# src/devops_cli/design/tokens-*.{css,json} (docs/DESIGN.md, "Token pipeline").
.PHONY: design-tokens
design-tokens:
	$(STYLE_DICTIONARY) build -c design/sd/base.json
	$(STYLE_DICTIONARY) build -c design/sd/light.json
	$(STYLE_DICTIONARY) build -c design/sd/dark.json
	$(STYLE_DICTIONARY) build -c design/sd/dark-explicit.json

# The service dashboards: each spec of k8s/monitoring/dashboards/services.toml to
# k8s/monitoring/dashboards/<uid>.json, with the SRE template of
# src/devops_cli/grafana/service_dashboard.py and the Grafana Foundation SDK of the dependency
# group `dashboards` (docs/DESIGN.md, "Grafana").
.PHONY: dashboards
dashboards:
	uv run --group dashboards python -m devops_cli.grafana.service_dashboard k8s/monitoring/dashboards/services.toml

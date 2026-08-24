# Knowledge Base: Grafana (Observability & Telemetry Visualization)

## 1. Overview & Purpose

Grafana is the open-source analytics and interactive visualization web application. In the `devops-cli` ecosystem, Grafana visualizes workstation metrics collected by Prometheus, distributed traces from Jaeger / OpenTelemetry, container health metrics, and CLI subcommand execution performance.

---

## 2. Usage Information & Architecture

- **Automated Provisioning**: Configured with automated datasource provisioning for Prometheus (`http://prometheus-server.monitoring.svc:80`) and Jaeger.
- **Pre-baked Workstation Dashboards**: Provides dashboards for workstation CPU/memory metrics, Kubernetes cluster utilization, and DevOps CLI command execution latency.
- **CLI Subcommand**: `devops grafana` provides dashboard listing, datasource testing, and dashboard export.

---

## 3. Common & Advanced Commands

### DevOps CLI Grafana Commands
```bash
# List available dashboards and provisioned panels
devops grafana dashboards

# Test Grafana server connectivity and datasource health
devops grafana status
```

### Standard Grafana API & Port-Forwarding Commands
```bash
# Port-forward Grafana to local workstation port 3000
kubectl port-forward svc/grafana -n monitoring 3000:80

# Query Grafana API for active datasources
curl -s -u admin:admin http://localhost:3000/api/datasources | jq .

# Export a dashboard JSON definition
curl -s -u admin:admin http://localhost:3000/api/dashboards/uid/devops-cli-overview | jq . > dashboard.json
```

### Sample Dashboard Provisioning Manifest
```yaml
apiVersion: 1
providers:
  - name: "DevOps CLI Dashboards"
    orgId: 1
    folder: "DevOps"
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    options:
      path: /var/lib/grafana/dashboards
```

---

## 4. Best Practice Guidance

1. **Declarative Dashboard Provisioning**: Manage dashboards as JSON files in Git (`dashboards/`) and provision them declaratively rather than creating them ad-hoc in the UI.
2. **Standard Variable Filters**: Include template variables (`$namespace`, `$pod`, `$interval`) in all dashboards to enable fast scoping and exploration.
3. **Alert Rule Consistency**: Configure alerting rules alongside panel definitions using unified Alertmanager endpoints.
4. **Time Range Scoping**: Set default dashboard time ranges to relative values (`now-1h` to `now`) with auto-refresh intervals of 10s–30s.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Default Credential Rotation**: Change default `admin:admin` credentials upon initial stack deployment.
- **Anonymous Access**: Disable anonymous access (`auth.anonymous.enabled = false`) in production or shared environments.
- **TLS Termination**: Enforce TLS encryption on all external ingress endpoints.

---

## 6. General Standards & Reference Guidelines

- **Port Conventions**: Internal container port `3000`, service port `80`.
- **Datasource Naming**: Standardized datasource identifiers: `Prometheus` (default metrics) and `Jaeger` (default traces).

"""Pydantic resource models for Kubernetes subsystem operations and CLI functions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PodInfo(BaseModel):
    """Information for a Kubernetes Pod."""

    name: str = Field(..., description="Pod name")
    namespace: str = Field(default="default", description="Kubernetes namespace")
    status: str = Field(
        default="Unknown", description="Pod phase status (Running, Pending, Failed)"
    )
    ready_containers: str = Field(default="0/0", description="Fraction of ready containers")
    restart_count: int = Field(default=0, description="Total container restarts count")
    node_name: str | None = Field(default=None, description="Assigned Kubernetes node name")
    ip_address: str | None = Field(default=None, description="Assigned Pod IP address")
    age_seconds: int = Field(default=0, description="Pod uptime in seconds")


class K8sPodsRequest(BaseModel):
    """Request parameters for querying Kubernetes Pods."""

    namespace: str = Field(default="", description="Namespace filter (empty for all namespaces)")
    label_selector: str = Field(default="", description="Kubernetes label selector filter")
    field_selector: str = Field(default="", description="Kubernetes field selector filter")


class K8sPodsResult(BaseModel):
    """Result payload for Kubernetes Pod queries."""

    pods: list[PodInfo] = Field(
        default_factory=list, description="List of matching Kubernetes Pods"
    )
    total_pods: int = Field(default=0, description="Total number of Pods discovered")
    running_pods: int = Field(default=0, description="Number of Pods in Running state")
    failed_pods: int = Field(default=0, description="Number of Pods in Failed or CrashLoop state")


class K8sClusterStatusRequest(BaseModel):
    """Request parameters for Kubernetes cluster health check."""

    timeout_seconds: float = Field(default=10.0, description="API server response timeout")


class K8sClusterStatusResult(BaseModel):
    """Health check status and connectivity summary for active Kubernetes cluster."""

    connected: bool = Field(default=False, description="Whether the cluster API is reachable")
    cluster_name: str = Field(default="", description="Active Kubernetes cluster name")
    api_server_url: str = Field(default="", description="API server endpoint URL")
    server_version: str = Field(default="", description="Kubernetes control plane version")
    node_count: int = Field(default=0, description="Total number of cluster nodes")
    ready_nodes: int = Field(default=0, description="Number of nodes in Ready condition")
    namespaces_count: int = Field(default=0, description="Total count of active namespaces")
    healthy: bool = Field(default=False, description="Overall cluster operational health status")
    components: dict[str, str] = Field(
        default_factory=dict, description="Control plane component health states"
    )


class K8sBootstrapRequest(BaseModel):
    """Request parameters for bootstrapping a local Minikube / K8s cluster."""

    driver: str = Field(default="docker", description="Minikube driver (docker, kvm2, hyperkit)")
    cpus: int = Field(default=4, description="Allocated CPU cores")
    memory_mb: int = Field(default=8192, description="Allocated memory in MB")
    enable_gpu: bool = Field(default=False, description="Request GPU passthrough if available")
    profile: str = Field(default="minikube", description="Minikube cluster profile name")


class K8sBootstrapResult(BaseModel):
    """Result from local Kubernetes bootstrap operation."""

    success: bool = Field(default=True, description="Whether bootstrap succeeded")
    cluster_name: str = Field(default="minikube", description="Created cluster profile name")
    driver: str = Field(default="docker", description="Underlying virtualization driver")
    ip_address: str = Field(default="", description="Cluster node IP address")
    kubeconfig_path: str = Field(default="", description="Path to active kubeconfig")
    duration_seconds: float = Field(default=0.0, description="Elapsed provisioning runtime")


class K8sDeployStackRequest(BaseModel):
    """Request parameters for deploying infrastructure stacks to Kubernetes."""

    stack_name: str = Field(
        ..., description="Stack identifier (llm, telemetry, ingress, argocd, devops)"
    )
    namespace: str = Field(default="default", description="Target deployment namespace")
    values_override: dict[str, Any] = Field(
        default_factory=dict, description="Custom Helm values overrides"
    )


class K8sDeployStackResult(BaseModel):
    """Deployment result for a Kubernetes application stack."""

    stack_name: str = Field(..., description="Stack identifier deployed")
    namespace: str = Field(default="default", description="Target namespace")
    resources_created: list[str] = Field(
        default_factory=list, description="Manifest resources applied"
    )
    endpoints: dict[str, str] = Field(
        default_factory=dict, description="Discovered service endpoints and ports"
    )
    success: bool = Field(default=True, description="Whether all stack resources deployed cleanly")


class K8sTeardownStackRequest(BaseModel):
    """Request parameters for tearing down an infrastructure stack."""

    stack_name: str = Field(..., description="Stack identifier to teardown")
    namespace: str = Field(default="default", description="Target namespace")
    delete_pvc: bool = Field(default=False, description="Purge persistent volume claims")


class K8sTeardownStackResult(BaseModel):
    """Teardown result for a Kubernetes application stack."""

    stack_name: str = Field(..., description="Stack identifier torn down")
    namespace: str = Field(default="default", description="Target namespace")
    resources_deleted: list[str] = Field(
        default_factory=list, description="Manifest resources removed"
    )
    success: bool = Field(default=True, description="Whether teardown completed cleanly")


class PolicyRuleViolation(BaseModel):
    """Detailed violation record for a failed Kubernetes admission policy rule."""

    policy_name: str = Field(..., description="Kyverno or OPA Gatekeeper policy name")
    rule_name: str = Field(..., description="Evaluated policy rule name")
    resource_kind: str = Field(..., description="Target Kubernetes resource kind")
    resource_name: str = Field(..., description="Target Kubernetes resource name")
    severity: str = Field(default="HIGH", description="Violation severity rating")
    message: str = Field(..., description="Detailed violation message and remediation advice")


class K8sPolicyValidateRequest(BaseModel):
    """Request parameters for validating Kubernetes manifests against admission policies."""

    manifest_path: str = Field(..., description="Path to manifest file or directory")
    policy_engine: str = Field(default="kyverno", description="Engine to use (kyverno | opa)")


class K8sPolicyValidateResult(BaseModel):
    """Validation report from Kubernetes admission policy evaluation."""

    manifest_path: str = Field(..., description="Validated manifest path")
    passed: bool = Field(default=True, description="Whether all manifests comply with policies")
    total_rules_evaluated: int = Field(default=0, description="Number of rules evaluated")
    violations_count: int = Field(default=0, description="Total count of policy violations")
    violations: list[PolicyRuleViolation] = Field(
        default_factory=list, description="Policy violation details"
    )


class K8sJaegerInfoRequest(BaseModel):
    """Request parameters for querying Jaeger tracing instance details in Kubernetes."""

    namespace: str = Field(default="telemetry", description="Namespace containing Jaeger")


class K8sJaegerInfoResult(BaseModel):
    """Information for Jaeger distributed tracing collector and UI endpoints."""

    ui_url: str = Field(default="", description="Jaeger Web UI endpoint URL")
    collector_otlp_grpc: str = Field(
        default="", description="OTLP gRPC collector endpoint (e.g. host:4317)"
    )
    collector_otlp_http: str = Field(
        default="", description="OTLP HTTP collector endpoint (e.g. host:4318)"
    )
    status: str = Field(default="Running", description="Collector deployment status")
    available: bool = Field(default=False, description="Whether Jaeger endpoints are accessible")

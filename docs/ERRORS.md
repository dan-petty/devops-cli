# DevOps CLI Exit Code & Error Catalog

This document provides the canonical machine-readable error codes, POSIX exit status codes,
and domain categorization for all exceptions inheriting from `DevOpsCLIError`.

## Standard Process Exit Codes

| Exit Code | Constant | Meaning |
|---|---|---|
| `0` | `CONST_EXIT_SUCCESS` | Command completed successfully with zero defects or violations. |
| `1` | `CONST_EXIT_FAILURE` | General operational failure, unhandled runtime defect, or schema violation. |
| `2` | `CONST_EXIT_USAGE` | Invalid CLI arguments, missing parameters, or syntax validation error. |
| `130` | `CONST_EXIT_CANCELLED` | Execution interrupted by user signal (`SIGINT` / `Ctrl+C`). |

---

## Subsystem Error Code Matrix

An error code may be shared by a base class and its subclasses; the exception column
names the class each row describes. One code never maps to two exit statuses.

Each exception class declares its `error_code` and `exit_code`. A command that a `DevOpsCLIError` ends prints one error line and exits with the exception's `exit_code`; an exception raised for a failed subprocess can carry that subprocess's own status instead.

| Exception | Error Code | Exit Code | Domain | Description |
|---|---|---|---|---|
| `AIClientError` | `LLM_INFERENCE_ERROR` | `10` | Devops_cli.ai.client.models | Raised when an AI provider request fails with a user-actionable message. |
| `AICredentialsError` | `LLM_INFERENCE_ERROR` | `10` | Devops_cli.ai.client.models | Raised when a provider rejects the request's credentials; retrying cannot help. |
| `ApprovalRequired` | `APPROVAL_REQUIRED` | `17` | Ai | Raised by a tool or validator when human approval is required to proceed. |
| `ArgoCDGateError` | `ARGOCD_GATE_ERROR` | `1` | K8s | Raised when an Argo CD application fails offline build, value, or placeholder validation (#1343). |
| `ArgoError` | `ARGO_ERROR` | `1` | Argo | Base exception for Argo CD, Rollouts, and Workflows operations. |
| `ArgoResourceNotFoundError` | `ARGO_RESOURCE_NOT_FOUND` | `1` | Argo | Raised when an Argo custom resource does not exist in the target cluster. |
| `BranchAlreadyExistsError` | `BRANCH_ALREADY_EXISTS` | `1` | Git | Raised when attempting to create a branch that already exists. |
| `CallDeferred` | `CALL_DEFERRED` | `18` | Ai | Raised by a tool when execution is deferred to an external worker or async system. |
| `CapabilityDegradationError` | `CAPABILITY_DEGRADATION` | `1` | Ai | Raised when a fallback or failover model breaches minimum capability tier requirements. |
| `ChaosExecutionError` | `CHAOS_EXECUTION_ERROR` | `1` | K8s | Raised when chaos engineering injection or validation fails. |
| `ChecksumMismatchError` | `CHECKSUM_MISMATCH` | `1` | Tools | Raised when downloaded tool archive SHA-256 does not match expected checksum. |
| `CloudflareAPIError` | `CLOUDFLARE_API_ERROR` | `1` | Cloudflare | Raised when a Cloudflare API call returns an error response. |
| `CloudflareAuthError` | `CLOUDFLARE_AUTH_ERROR` | `1` | Cloudflare | Raised when Cloudflare authentication or token verification fails. |
| `CloudflareError` | `CLOUDFLARE_ERROR` | `1` | Cloudflare | Base exception for Cloudflare domain errors. |
| `ClusterJobError` | `K8S_CLUSTER_JOB_ERROR` | `1` | K8s | Raised when a devops-cli Job cannot be created or followed in the cluster. |
| `ClusterSecretPushError` | `K8S_SECRET_PUSH_ERROR` | `1` | K8s | Raised when cluster Secrets cannot be pushed from the keyring; nothing was written. |
| `ClusterSecretWriteError` | `K8S_SECRET_PUSH_ERROR` | `1` | K8s | Raised when writing a planned push fails part-way; `completed` names what was written. |
| `ConfigurationError` | `CONFIGURATION_ERROR` | `1` | Config | Base exception for configuration loading, validation, and serialization errors. |
| `CosignError` | `COSIGN_ERROR` | `1` | Docker | Raised when Sigstore Cosign image signing fails. |
| `CosignVerificationError` | `COSIGN_VERIFICATION_FAILED` | `1` | Docker | Raised when Sigstore Cosign signature or attestation verification fails. |
| `DependencyError` | `DEPENDENCY_MISSING` | `1` | Tools | Raised when a required external binary/dependency is missing from the system PATH. |
| `DockerDaemonUnavailableError` | `DOCKER_DAEMON_UNAVAILABLE` | `1` | Docker | Raised when the Docker daemon socket cannot be reached or negotiated. |
| `DockerEngineError` | `DOCKER_ENGINE_ERROR` | `1` | Docker | Raised when a Docker Engine API call over the daemon socket fails. |
| `DockerError` | `DOCKER_ERROR` | `1` | Docker | Base exception for Docker operations. |
| `DockerSandboxError` | `DOCKER_SANDBOX_ERROR` | `1` | Docker | Raised when docker sandbox execution, container creation, or termination fails. |
| `DocsIngestionError` | `DOCS_INGESTION_ERROR` | `1` | Ai | Base exception for documentation ingestion errors. |
| `DoctorCheckError` | `K8S_DOCTOR_CHECK_FAILED` | `1` | K8s | Raised inside `devops k8s doctor --stack` when one check fails; the message is its reason. |
| `EmbeddingsError` | `EMBEDDINGS_ERROR` | `1` | Devops_cli.ai.rag.embeddings | Raised when embeddings generation fails across all endpoints. |
| `GatewayTuneError` | `DEVOPS_CLI_ERROR` | `1` | Devops_cli.ai.gateway_tune | Raised when the gateway's deployments cannot be discovered or measured. |
| `GitHubFileNotFoundError` | `GITHUB_FILE_NOT_FOUND` | `1` | Git | Raised when a repository file GitHub was asked for does not exist on that ref. |
| `GitHubNotFoundError` | `GITHUB_NOT_FOUND` | `1` | Git | Raised when GitHub answers that what it was asked for does not exist (HTTP 404). |
| `GitHubOperationError` | `GITHUB_OPERATION_FAILED` | `1` | Git | Exception raised for GitHub API or CLI automation failures. |
| `GitHubRateLimitError` | `GITHUB_RATE_LIMIT_UNKNOWN` | `1` | Git | Exception raised when GitHub rate limit quota state is broken or unknown and cannot be resolved. |
| `GitHubScopeError` | `GITHUB_SCOPE_MISSING` | `1` | Git | Raised when GitHub refuses a request because the token lacks a scope the endpoint needs. |
| `GitHubUnauthenticatedError` | `GITHUB_UNAUTHENTICATED` | `1` | Git | Raised when the process has no GitHub identity, or GitHub refused its token (HTTP 401). |
| `GitHubUnreadError` | `GITHUB_UNREAD` | `1` | Git | Raised when no answer from GitHub could be read, so what the request did is unknown. |
| `GitOperationError` | `GIT_OPERATION_ERROR` | `1` | Git | Base exception for Git repository and branch operation failures. |
| `HTTPTimeoutTypeError` | `VALIDATION_ERROR` | `1` | Devops_cli.http.client | Raised when an invalid timeout parameter type is provided. |
| `HarnessValidationError` | `HARNESS_VALIDATION_ERROR` | `1` | Ai | Raised when an AI evaluation or harness schema validation fails. |
| `ImagePinError` | `K8S_IMAGE_PIN_ERROR` | `1` | K8s | Raised when an image that an Argo CD Application pins does not resolve in its registry, or an |
| `ImplementEvalError` | `ROADMAP_EVAL_REFUSED` | `1` | Roadmap | Raised when `devops roadmap eval implement` cannot read or use a fixture, or is asked for |
| `InvalidBranchNameError` | `INVALID_BRANCH_NAME` | `1` | Git | Raised when a proposed Git branch name violates naming conventions. |
| `InvalidURLError` | `INVALID_URL` | `1` | Validation | Raised when an invalid URL or URI scheme is provided. |
| `KeyringUnavailableError` | `KEYRING_UNAVAILABLE` | `3` | Security | Raised when the OS Keyring service is unreachable or uninitialized. |
| `KubernetesContextError` | `K8S_CONTEXT_ERROR` | `1` | K8s | Raised when a Kubernetes context cannot be resolved or is invalid. |
| `KubernetesDeployError` | `K8S_DEPLOY_ERROR` | `1` | K8s | Raised when deploying manifests or Helm charts fails. |
| `KubernetesError` | `K8S_ERROR` | `1` | K8s | Base exception for Kubernetes operations. |
| `KubernetesLoggingError` | `K8S_LOGGING_ERROR` | `1` | K8s | Raised when querying cluster logs or Loki fails. |
| `KubernetesTunnelError` | `K8S_TUNNEL_ERROR` | `1` | K8s | Raised when `devops k8s tunnel` cannot start, find or stop its forward (#1641). |
| `LLMInferenceError` | `LLM_INFERENCE_ERROR` | `10` | Ai | Base exception for LLM provider invocation failures. |
| `LibraryIngestionError` | `LIBRARY_INGESTION_ERROR` | `1` | Ai | Base exception for package introspection and library ingestion errors. |
| `LibraryNotFoundError` | `LIBRARY_NOT_FOUND_ERROR` | `1` | Ai | Raised when target package could not be loaded or found in the environment. |
| `LogfireConfigurationError` | `LOGFIRE_CONFIG_ERROR` | `1` | Telemetry | Raised when Logfire configuration fails or credentials cannot be retrieved. |
| `MemoryProfilerError` | `PROFILER_ERROR` | `1` | Devops_cli.telemetry.memory_profiler | Domain exception raised when memory profiling target resolution or execution fails. |
| `ModelBundleError` | `MODEL_BUNDLE_ERROR` | `1` | Ai | Raised when an AI model bundle cannot be located, resolved, or loaded. |
| `ModelGatewayUnreachableError` | `MODEL_GATEWAY_UNREACHABLE` | `1` | Ai | Raised when a model call through the gateway fails, so the command decided and wrote nothing. |
| `ModelNotAllowedError` | `MODEL_REQUESTS_DISABLED` | `1` | Devops_cli.ai.agents.testing | Raised when a non-test model request is attempted while ALLOW_MODEL_REQUESTS is False. |
| `ModelRetry` | `MODEL_RETRY_REQUESTED` | `14` | Ai | Raised by tools or output validators to request the model to retry with corrective feedback. |
| `OtlpExportError` | `TELEMETRY_ERROR` | `1` | Telemetry | Raised when the collector does not take an OTLP export, with the failure as its message. |
| `OtlpProtocolError` | `TELEMETRY_ERROR` | `1` | Telemetry | Raised when the OTLP protocol or endpoint asks for gRPC, which devops-cli does not send. |
| `OutputCapReached` | `OUTPUT_CAP_REACHED` | `15` | Ai | A model reply ended with the finish reason `length`: the model did not stop, and the output |
| `PoolLoadError` | `DEVOPS_CLI_ERROR` | `1` | Devops_cli.ai.pool_load | Prometheus could not answer a pool load query. |
| `QdrantClientError` | `DEVOPS_CLI_ERROR` | `1` | Devops_cli.ai.rag.qdrant | Raised when an interaction with Qdrant fails. |
| `RegistryReadError` | `DOCKER_REGISTRY_READ_ERROR` | `1` | Docker | Raised when an image registry gives no digest for a tag: no anonymous pull, or no tag. |
| `ReplyRejectedError` | `LLM_INFERENCE_ERROR` | `10` | Devops_cli.ai.client.models | Raised when the caller's validator refused a reply; it carries the reply, never cached. |
| `ReviewHandOffRefusedError` | `REVIEW_HAND_OFF_REFUSED` | `1` | Ai | Raised when `devops review intake` refuses a session that is not on merged code. |
| `ReviewPoolError` | `REVIEW_POOL_ERROR` | `1` | Ai | Raised when an error occurs during parallel review worker pool execution. |
| `ReviewSessionExistsError` | `REVIEW_SESSION_EXISTS` | `1` | Ai | Raised when a review is published under the name of a session that is already published. |
| `ReviewStateError` | `REVIEW_STATE_ERROR` | `1` | Devops_cli.review.state | Exception raised for invalid review finding state or state transition. |
| `RoadmapAlternativesError` | `ROADMAP_ALTERNATIVES_FAILED` | `1` | Roadmap | Raised after an alternatives run that tried items and checked none of them. |
| `RoadmapClaimError` | `ROADMAP_ITEM_CLAIMED` | `1` | Roadmap | Raised when a claim of a roadmap Item is refused, because another owner holds it or |
| `RoadmapImplementError` | `ROADMAP_IMPLEMENT_REFUSED` | `1` | Roadmap | Raised when `devops roadmap implement` refuses to start a step, or cannot read its inputs. |
| `RoadmapIntakeError` | `ROADMAP_INTAKE_FAILED` | `1` | Roadmap | Raised after an intake round in which the writes failed for one or more candidates. |
| `RoadmapItemChangedError` | `ROADMAP_ITEM_CHANGED` | `1` | Roadmap | Raised before a job's field write that would revert a change made since it read the Item. |
| `RoadmapRefineError` | `ROADMAP_REFINE_FAILED` | `1` | Roadmap | Raised after a refine run in which the model call failed for one or more items. |
| `RoadmapRunError` | `DEVOPS_CLI_ERROR` | `1` | Roadmap | Raised when one or more roadmap jobs fail during execution. |
| `RoadmapStageError` | `ROADMAP_STAGE_FAILED` | `1` | Roadmap | Raised after a stage run in which one or more items failed (#2654). |
| `RunIndexNotConfiguredError` | `DEVOPS_CLI_ERROR` | `1` | Devops_cli.ai.run_store | No shared run index is configured. |
| `SSHRegistrationError` | `GITHUB_OPERATION_FAILED` | `1` | Devops_cli.github.ssh | Raised when SSH/signing key registration on GitHub fails. |
| `SSRFBlockedError` | `SSRF_BLOCKED` | `2` | Security | Raised when an outbound HTTP request targets a private or forbidden network IP. |
| `SandboxError` | `SANDBOX_ERROR` | `1` | Sandbox | Base exception for workload sandbox lifecycle operations. |
| `SandboxNotFoundError` | `SANDBOX_NOT_FOUND_ERROR` | `1` | Sandbox | Raised when requested sandbox instance or container cannot be found. |
| `SandboxPortAllocationError` | `SANDBOX_PORT_ALLOCATION_ERROR` | `1` | Sandbox | Raised when host port allocation encounters collisions or range exhaustion. |
| `SandboxUnavailableError` | `SANDBOX_UNAVAILABLE_ERROR` | `1` | Sandbox | Raised when this host cannot start the sandbox of a review tool, so the tool does not run. |
| `SandboxValidationError` | `SANDBOX_VALIDATION_ERROR` | `1` | Sandbox | Raised when sandbox configuration or directory mount paths violate security boundaries. |
| `SecurityError` | `SECURITY_ERROR` | `1` | Security | Base exception for all security, policy, and egress violations. |
| `ServiceAddressError` | `K8S_ERROR` | `1` | Devops_cli.k8s.service_proxy | Raised when a cluster service address cannot be resolved. |
| `ServiceNotReachableError` | `DEVOPS_CLI_ERROR` | `1` | Devops_cli.k8s.node_port | A service cannot be reached from outside the cluster. |
| `ServiceStatusError` | `SERVICE_STATUS_ERROR` | `1` | Telemetry | Raised when querying upstream published service status fails. |
| `ServiceStoppingError` | `SERVICE_STOPPING` | `1` | Roadmap | Raised when a request ends because the Service is stopping (#2753). |
| `StackCredentialError` | `K8S_STACK_CREDENTIAL_ERROR` | `1` | K8s | Raised when a stack credential cannot be read, checked, minted, revoked or stored (#2156). |
| `StructuredOutputSchemaError` | `STRUCTURED_OUTPUT_SCHEMA_INVALID` | `1` | Ai | Raised when a schema class is missing or invalid for structured LLM output generation. |
| `StructuredOutputValidationError` | `LLM_INFERENCE_ERROR` | `10` | Devops_cli.ai.client.models | Raised when the model answered, but no answer validated against the schema after retries. |
| `SubprocessError` | `SUBPROCESS_FAILED` | `1` | Tools | Raised when an external subprocess command exits with a non-zero code or fails execution. |
| `TelemetryError` | `TELEMETRY_ERROR` | `1` | Telemetry | Base exception for telemetry, tracing, and metric collection errors. |
| `TemplateRenderError` | `VALIDATION_ERROR` | `1` | Devops_cli.core.templating | Raised when a template cannot be rendered into valid output. |
| `ToolDownloadError` | `TOOL_DOWNLOAD_ERROR` | `1` | Tools | Raised when an external tool download fails or is rejected. |
| `ToolExecutionError` | `TOOL_EXECUTION_ERROR` | `1` | Tools | Base exception for external developer tool and binary execution failures. |
| `ToolFailed` | `TOOL_FAILED` | `16` | Ai | Raised when a tool encounters an unrecoverable runtime failure without requesting model retry. |
| `TraceValidationError` | `VALIDATION_ERROR` | `1` | Devops_cli.telemetry.context | Raised when trace metadata or flags fail validation. |
| `UnexpectedModelBehavior` | `UNEXPECTED_MODEL_BEHAVIOR` | `15` | Ai | Raised when model retry budget is exhausted or model emits unrecoverable response. |
| `ValidationError` | `VALIDATION_ERROR` | `1` | Validation | Base exception for user input and format validation failures. |
| `ValkeyAuthenticationError` | `VALKEY_AUTHENTICATION_ERROR` | `1` | Valkey | Raised when Valkey password authentication fails. |
| `ValkeyCommandError` | `VALKEY_COMMAND_ERROR` | `1` | Valkey | Raised when a Valkey command execution returns an error from server. |
| `ValkeyConnectionError` | `VALKEY_CONNECTION_ERROR` | `1` | Valkey | Raised when connection to Valkey instance fails, times out, or drops. |
| `ValkeyError` | `VALKEY_ERROR` | `1` | Valkey | Base exception for Valkey workstation and caching operations. |
| `ValkeyTimeoutError` | `VALKEY_TIMEOUT_ERROR` | `1` | Valkey | Raised when a Valkey socket operation exceeds timeout. |
| `VaultAuthenticationError` | `VAULT_AUTH_ERROR` | `1` | Vault | Raised when Vault issues or accepts no token: a failed login, none usable, or one refused. |
| `VaultConfigurationError` | `VAULT_CONFIGURATION_ERROR` | `1` | Vault | Raised when Vault environment or connection settings are missing or invalid. |
| `VaultError` | `VAULT_ERROR` | `1` | Vault | Base exception for HashiCorp Vault operations. |
| `VaultKeyError` | `VAULT_KEY_ERROR` | `1` | Vault | Raised when a secret key or field is not found in Vault. |
| `VaultLeaseError` | `VAULT_LEASE_ERROR` | `1` | Vault | Raised when a Vault lease, login or token call fails, with Vault's HTTP status. |
| `VaultOperationError` | `VAULT_OPERATION_ERROR` | `1` | Vault | Raised when an API request to Vault fails or returns an error response. |
| `VaultUnreachableError` | `VAULT_OPERATION_ERROR` | `1` | Vault | Raised when no reply came back from Vault: the connection failed or timed out. |
| `VolumeMoveError` | `K8S_VOLUME_MOVE_FAILED` | `1` | K8s | Raised when a volume move fails before the old claim is deleted; it undid its own steps. |
| `VolumeMoveRefusedError` | `K8S_VOLUME_MOVE_REFUSED` | `1` | K8s | Raised when a volume move cannot start safely; it changed nothing. |
| `VolumeMoveStrandedError` | `K8S_VOLUME_MOVE_STRANDED` | `1` | K8s | Raised when a volume move fails after the old claim was deleted; Argo CD stays paused. |
| `VolumeReclaimError` | `K8S_VOLUME_RECLAIM_ERROR` | `1` | K8s | Raised when volume reclaim fails or is refused due to active claims or mounts. |

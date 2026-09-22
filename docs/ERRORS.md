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

| Exception | Error Code | Exit Code | Domain | Description |
|---|---|---|---|---|
| `AIClientError` | `LLM_INFERENCE_ERROR` | `10` | Devops_cli.ai.client.models | Raised when an AI provider request fails with a user-actionable message. |
| `AgentRunError` | `AGENT_RUN_ERROR` | `20` | Ai | Raised when an error occurs during an agent run lifecycle. |
| `ApprovalRequired` | `APPROVAL_REQUIRED` | `17` | Ai | Raised by a tool or validator when human approval is required to proceed. |
| `ArgoError` | `ARGO_ERROR` | `1` | Argo | Base exception for Argo CD, Rollouts, and Workflows operations. |
| `ArgoResourceNotFoundError` | `ARGO_RESOURCE_NOT_FOUND` | `1` | Argo | Raised when an Argo custom resource does not exist in the target cluster. |
| `BranchAlreadyExistsError` | `BRANCH_ALREADY_EXISTS` | `1` | Git | Raised when attempting to create a branch that already exists. |
| `BudgetExceededError` | `BUDGET_EXCEEDED` | `1` | Devops_cli.ai.agents.spend | Raised when an agent execution exceeds defined token or financial spend limits. |
| `CallDeferred` | `CALL_DEFERRED` | `18` | Ai | Raised by a tool when execution is deferred to an external worker or async system. |
| `ChaosExecutionError` | `CHAOS_EXECUTION_ERROR` | `1` | K8s | Raised when chaos engineering injection or validation fails. |
| `ChecksumMismatchError` | `ChecksumMismatchError` | `1` | Tools | Raised when downloaded tool archive SHA-256 does not match expected checksum. |
| `ConcurrencyLimitExceeded` | `CONCURRENCY_LIMIT_EXCEEDED` | `25` | Ai | Raised when the concurrency queue depth exceeds max_queued. |
| `ConfigurationError` | `CONFIGURATION_ERROR` | `1` | Config | Base exception for configuration loading, validation, and serialization errors. |
| `ConstellationFailoverError` | `CONSTELLATION_FAILOVER_ERROR` | `1` | Ai | Raised when emergency failover routing fails. |
| `ConstellationQuiesceError` | `CONSTELLATION_QUIESCE_ERROR` | `1` | Ai | Raised when constellation quiesce suspension fails. |
| `ConstellationResumeError` | `CONSTELLATION_RESUME_ERROR` | `1` | Ai | Raised when resuming suspended constellation tasks fails. |
| `ContentFilterError` | `CONTENT_FILTER_TRIGGERED` | `19` | Ai | Raised when a model response is filtered or refused by upstream content safety filters. |
| `ContextBudgetExceededError` | `CONTEXT_BUDGET_EXCEEDED` | `11` | Ai | Raised when prompt token payload exceeds model context window limits. |
| `CosignError` | `COSIGN_ERROR` | `1` | Docker | Raised when Sigstore Cosign image signing fails. |
| `CosignVerificationError` | `COSIGN_VERIFICATION_FAILED` | `1` | Docker | Raised when Sigstore Cosign signature or attestation verification fails. |
| `DependencyError` | `DEPENDENCY_MISSING` | `1` | Tools | Raised when a required external binary/dependency is missing from the system PATH. |
| `DocCompactionError` | `DOC_COMPACTION_ERROR` | `1` | Docs | Exception raised when documentation compaction fails. |
| `DockerDaemonUnavailableError` | `DOCKER_DAEMON_UNAVAILABLE` | `1` | Docker | Raised when the Docker daemon socket cannot be reached or negotiated. |
| `DockerEngineError` | `DOCKER_ENGINE_ERROR` | `1` | Docker | Raised when a Docker Engine API call over the daemon socket fails. |
| `DockerError` | `DOCKER_ERROR` | `1` | Docker | Base exception for Docker operations. |
| `DockerSandboxError` | `DOCKER_SANDBOX_ERROR` | `1` | Docker | Raised when docker sandbox execution, container creation, or termination fails. |
| `DocsIngestionError` | `DOCS_INGESTION_ERROR` | `1` | Ai | Base exception for documentation ingestion errors. |
| `EmbeddingsError` | `EMBEDDINGS_ERROR` | `1` | Devops_cli.ai.rag.embeddings | Raised when embeddings generation fails across all endpoints. |
| `GitHubGraphQLError` | `GITHUB_GRAPHQL_ERROR` | `1` | Git | Exception raised when GitHub GraphQL queries or mutations fail. |
| `GitHubOperationError` | `GITHUB_OPERATION_FAILED` | `1` | Git | Exception raised for GitHub API or CLI automation failures. |
| `GitHubRateLimitError` | `GITHUB_RATE_LIMIT_UNKNOWN` | `1` | Git | Exception raised when GitHub rate limit quota state is broken or unknown and cannot be resolved. |
| `GitHubWebhookVerificationError` | `GITHUB_WEBHOOK_VERIFICATION_FAILED` | `1` | Git | Exception raised when GitHub webhook signature verification fails. |
| `GitOperationError` | `GIT_OPERATION_ERROR` | `1` | Git | Base exception for Git repository and branch operation failures. |
| `GitOpsSyncError` | `GITOPS_SYNC_ERROR` | `1` | K8s | Raised when GitOps synchronization trigger or reconciliation fails. |
| `HTTPTimeoutTypeError` | `VALIDATION_ERROR` | `1` | Devops_cli.http.client | Raised when an invalid timeout parameter type is provided. |
| `HarnessExecutionError` | `HARNESS_EXECUTION_ERROR` | `1` | Ai | Raised when execution of an AI test harness or benchmark fails. |
| `HarnessValidationError` | `HARNESS_VALIDATION_ERROR` | `1` | Ai | Raised when an AI evaluation or harness schema validation fails. |
| `IncompleteToolCall` | `INCOMPLETE_TOOL_CALL` | `27` | Ai | Raised when a model stops due to token limit while emitting a tool call. |
| `InsecureConfigError` | `E_INSECURE_CONFIG` | `126` | Security | Raised when an unencrypted plaintext secret token is found in configuration files. |
| `InvalidBranchNameError` | `INVALID_BRANCH_NAME` | `1` | Git | Raised when a proposed Git branch name violates naming conventions. |
| `InvalidURLError` | `INVALID_URL` | `1` | Validation | Raised when an invalid URL or URI scheme is provided. |
| `InvalidVersionError` | `INVALID_VERSION` | `1` | Validation | Raised when a semantic version string cannot be parsed. |
| `KeyringUnavailableError` | `KEYRING_UNAVAILABLE` | `3` | Security | Raised when the OS Keyring service is unreachable or uninitialized. |
| `KubernetesContextError` | `K8S_CONTEXT_ERROR` | `1` | K8s | Raised when a Kubernetes context cannot be resolved or is invalid. |
| `KubernetesDeployError` | `K8S_DEPLOY_ERROR` | `1` | K8s | Raised when deploying manifests or Helm charts fails. |
| `KubernetesError` | `K8S_ERROR` | `1` | K8s | Base exception for Kubernetes operations. |
| `KubernetesLoggingError` | `K8S_LOGGING_ERROR` | `1` | K8s | Raised when querying cluster logs or Loki fails. |
| `LLMInferenceError` | `LLM_INFERENCE_ERROR` | `10` | Ai | Base exception for LLM provider invocation failures. |
| `LibraryIngestionError` | `LIBRARY_INGESTION_ERROR` | `1` | Ai | Base exception for package introspection and library ingestion errors. |
| `LibraryNotFoundError` | `LIBRARY_NOT_FOUND_ERROR` | `1` | Ai | Raised when target package cannot be imported or found in the environment. |
| `LogfireConfigurationError` | `LOGFIRE_CONFIG_ERROR` | `1` | Telemetry | Raised when Logfire configuration fails or credentials cannot be retrieved. |
| `MemoryProfilerError` | `PROFILER_ERROR` | `1` | Devops_cli.telemetry.memory_profiler | Domain exception raised when memory profiling target resolution or execution fails. |
| `ModelAPIError` | `MODEL_API_ERROR` | `22` | Ai | Raised when a model provider API request fails. |
| `ModelBundleError` | `MODEL_BUNDLE_ERROR` | `1` | Ai | Raised when an AI model bundle cannot be located, resolved, or loaded. |
| `ModelHTTPError` | `MODEL_HTTP_ERROR` | `23` | Ai | Raised when a model provider response has a status code of 4xx or 5xx. |
| `ModelNotAllowedError` | `MODEL_REQUESTS_DISABLED` | `1` | Devops_cli.ai.agents.testing | Raised when a non-test model request is attempted while ALLOW_MODEL_REQUESTS is False. |
| `ModelRetry` | `MODEL_RETRY_REQUESTED` | `14` | Ai | Raised by tools or output validators to request the model to retry with corrective feedback. |
| `ModelUnavailableError` | `MODEL_UNAVAILABLE` | `12` | Ai | Raised when the requested LLM backend or model endpoint is unreachable. |
| `PersonaExecutionError` | `PERSONA_EXECUTION_ERROR` | `13` | Ai | Raised when an AI reviewer persona fails during diff analysis. |
| `QdrantClientError` | `DEVOPS_CLI_ERROR` | `1` | Devops_cli.ai.rag.qdrant | Raised when an interaction with Qdrant fails. |
| `ReviewPoolError` | `REVIEW_POOL_ERROR` | `1` | Ai | Raised when an error occurs during parallel review worker pool execution. |
| `RunCancelled` | `RUN_CANCELLED` | `26` | Ai | Raised when an agent run was cancelled by the application or timeout. |
| `SSRFBlockedError` | `SSRF_BLOCKED` | `2` | Security | Raised when an outbound HTTP request targets a private or forbidden network IP. |
| `SandboxError` | `SANDBOX_ERROR` | `1` | Sandbox | Base exception for workload sandbox lifecycle operations. |
| `SandboxNotFoundError` | `SANDBOX_NOT_FOUND_ERROR` | `1` | Sandbox | Raised when requested sandbox instance or container cannot be found. |
| `SandboxPortAllocationError` | `SANDBOX_PORT_ALLOCATION_ERROR` | `1` | Sandbox | Raised when host port allocation encounters collisions or range exhaustion. |
| `SandboxValidationError` | `SANDBOX_VALIDATION_ERROR` | `1` | Sandbox | Raised when sandbox configuration or directory mount paths violate security boundaries. |
| `SecretExposureError` | `SecretExposureError` | `1` | Security | Raised when an unmasked credential or private key is detected in uncommitted diffs. |
| `SecurityError` | `SECURITY_ERROR` | `1` | Security | Base exception for all security, policy, and egress violations. |
| `ServiceAddressError` | `K8S_ERROR` | `1` | Devops_cli.k8s.service_proxy | Raised when a cluster service address cannot be resolved. |
| `StructuredOutputSchemaError` | `STRUCTURED_OUTPUT_SCHEMA_INVALID` | `1` | Ai | Raised when a schema class is missing or invalid for structured LLM output generation. |
| `SubprocessError` | `SUBPROCESS_FAILED` | `1` | Tools | Raised when an external subprocess command exits with a non-zero code or fails execution. |
| `SuspendedResponseExpired` | `SUSPENDED_RESPONSE_EXPIRED` | `28` | Ai | Raised when resuming a suspended response whose server-side job is no longer available. |
| `TelemetryError` | `TELEMETRY_ERROR` | `1` | Telemetry | Base exception for telemetry, tracing, and metric collection errors. |
| `TemplateRenderError` | `VALIDATION_ERROR` | `1` | Devops_cli.core.templating | Raised when a template cannot be rendered into valid output. |
| `ToolDownloadError` | `ToolDownloadError` | `1` | Tools | Raised when an external tool download fails or is rejected. |
| `ToolExecutionError` | `TOOL_EXECUTION_ERROR` | `1` | Tools | Base exception for external developer tool and binary execution failures. |
| `ToolFailed` | `TOOL_FAILED` | `16` | Ai | Raised when a tool encounters an unrecoverable runtime failure without requesting model retry. |
| `TraceValidationError` | `VALIDATION_ERROR` | `1` | Devops_cli.telemetry.context | Raised when trace metadata or flags fail validation. |
| `UnexpectedModelBehavior` | `UNEXPECTED_MODEL_BEHAVIOR` | `15` | Ai | Raised when model retry budget is exhausted or model emits unrecoverable response. |
| `UsageLimitExceeded` | `USAGE_LIMIT_EXCEEDED` | `24` | Ai | Raised when an agent run exceeds configured request or token limits. |
| `UserError` | `USER_ERROR` | `21` | Ai | Raised when an invalid configuration or argument is provided by the application developer. |
| `ValidationError` | `VALIDATION_ERROR` | `1` | Validation | Base exception for user input and format validation failures. |
| `ValkeyAuthenticationError` | `VALKEY_AUTHENTICATION_ERROR` | `1` | Valkey | Raised when Valkey password authentication fails. |
| `ValkeyCommandError` | `VALKEY_COMMAND_ERROR` | `1` | Valkey | Raised when a Valkey command execution returns an error from server. |
| `ValkeyConnectionError` | `VALKEY_CONNECTION_ERROR` | `1` | Valkey | Raised when connection to Valkey instance fails, times out, or drops. |
| `ValkeyError` | `VALKEY_ERROR` | `1` | Valkey | Base exception for Valkey workstation and caching operations. |
| `ValkeyTimeoutError` | `VALKEY_TIMEOUT_ERROR` | `1` | Valkey | Raised when a Valkey socket operation exceeds timeout. |
| `VaultAuthenticationError` | `VAULT_AUTH_ERROR` | `1` | Vault | Raised when a Vault login method fails to issue a client token. |
| `VaultConfigurationError` | `VAULT_CONFIGURATION_ERROR` | `1` | Vault | Raised when Vault environment or connection settings are missing or invalid. |
| `VaultError` | `VAULT_ERROR` | `1` | Vault | Base exception for HashiCorp Vault operations. |
| `VaultKeyError` | `VAULT_KEY_ERROR` | `1` | Vault | Raised when a secret key or field is not found in Vault. |
| `VaultLeaseError` | `VAULT_LEASE_ERROR` | `1` | Vault | Raised when a dynamic secret lease cannot be renewed or revoked. |
| `VaultOperationError` | `VAULT_OPERATION_ERROR` | `1` | Vault | Raised when an API request to Vault fails or returns an error response. |

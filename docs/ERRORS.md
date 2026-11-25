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
| `AIClientError` | `LLM_INFERENCE_ERROR` | `10` | Ai | Raised when an AI provider request fails with a user-actionable message. |
| `AICredentialsError` | `LLM_INFERENCE_ERROR` | `10` | Ai | Raised when a provider rejects the request's credentials; retrying cannot help. |
| `AIKeySpendLimitError` | `LLM_INFERENCE_ERROR` | `10` | Ai | Raised when the provider key behind a request reached its spend limit (#6821). |
| `AgentAuditFilingError` | `AGENT_AUDIT_FILING_FAILED` | `1` | Core | Raised when `devops roadmap intake` does not file one draft of `devops ai agent-audit` (#2346). |
| `AnswerFlagError` | `ONBOARD_ANSWER_DIFFERS` | `2` | Github | A flag gives an answer that differs from `.copier-answers.yml` of the repository. |
| `ApplicationSourceError` | `K8S_APPLICATION_SOURCE_ERROR` | `1` | K8s | Raised when a git source of an Argo CD Application cannot be read (#5131). |
| `ApprovalRequired` | `APPROVAL_REQUIRED` | `17` | Ai | Raised by a tool or validator when human approval is required to proceed. |
| `ArgoCDGateError` | `ARGOCD_GATE_ERROR` | `1` | K8s | Raised when an Argo CD application fails offline build, value, or placeholder validation (#1343). |
| `ArgoError` | `ARGO_ERROR` | `1` | Argo | Base exception for Argo CD, Rollouts, and Workflows operations. |
| `ArgoResourceNotFoundError` | `ARGO_RESOURCE_NOT_FOUND` | `1` | Argo | Raised when an Argo custom resource does not exist in the target cluster. |
| `ArgoWorkflowTimeoutError` | `ARGO_WORKFLOW_TIMEOUT` | `1` | Argo | Raised when an Argo Workflow does not reach a terminal phase within the wait budget. |
| `BaselineUnreadableError` | `ONBOARD_BASELINE_UNREADABLE` | `1` | Github | The baseline cannot be read: no ref, no `copier` program, a failed render, or a settings file that the schema refuses. `step` is the person step that makes it readable, if any. |
| `BranchAlreadyExistsError` | `BRANCH_ALREADY_EXISTS` | `1` | Git | Raised when attempting to create a branch that already exists. |
| `CallDeferred` | `CALL_DEFERRED` | `18` | Ai | Raised by a tool when execution is deferred to an external worker or async system. |
| `CapabilityDegradationError` | `CAPABILITY_DEGRADATION` | `1` | Ai | Raised when a fallback or failover model breaches minimum capability tier requirements. |
| `CatalogError` | `K8S_CATALOG_ERROR` | `1` | K8s | Raised when `devops k8s catalog` finds catalog, SLO, dashboard, or workload mismatches (#5535). |
| `ChaosExecutionError` | `CHAOS_EXECUTION_ERROR` | `1` | K8s | Raised when chaos engineering injection or validation fails. |
| `CloudflareAPIError` | `CLOUDFLARE_API_ERROR` | `1` | Cloudflare | Raised when a Cloudflare API call returns an error response. |
| `CloudflareAuthError` | `CLOUDFLARE_AUTH_ERROR` | `1` | Cloudflare | Raised when Cloudflare authentication or token verification fails. |
| `CloudflareError` | `CLOUDFLARE_ERROR` | `1` | Cloudflare | Base exception for Cloudflare domain errors. |
| `ClusterJobError` | `K8S_CLUSTER_JOB_ERROR` | `1` | K8s | Raised when a devops-cli Job cannot be created or followed in the cluster. |
| `ClusterJobExistsError` | `K8S_CLUSTER_JOB_EXISTS` | `1` | K8s | Raised when the create of a Job gets 409: a Job of that name exists already. |
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
| `DocsSiteError` | `DOCS_SITE_INVALID` | `1` | Validation | Raised when the docs site cannot be staged, or when its built pages fail a check. |
| `DoctorCheckError` | `K8S_DOCTOR_CHECK_FAILED` | `1` | K8s | Raised inside `devops k8s doctor --stack` when one check fails; the message is its reason. |
| `EmbeddingsError` | `EMBEDDINGS_ERROR` | `1` | Ai | Raised when embeddings generation fails across all endpoints. |
| `GatewayTuneError` | `DEVOPS_CLI_ERROR` | `1` | Ai | Raised when the gateway's deployments cannot be discovered or measured. |
| `GitHubApiAccessRefusedError` | `GITHUB_API_ACCESS_REFUSED` | `1` | Git | Raised when an agent caller attempts a protected mutating `devops gh api` request (#5316). |
| `GitHubFileNotFoundError` | `GITHUB_FILE_NOT_FOUND` | `1` | Git | Raised when a repository file GitHub was asked for does not exist on that ref. |
| `GitHubNotFoundError` | `GITHUB_NOT_FOUND` | `1` | Git | Raised when GitHub answers that what it was asked for does not exist (HTTP 404). |
| `GitHubOperationError` | `GITHUB_OPERATION_FAILED` | `1` | Git | Exception raised for GitHub API or CLI automation failures. |
| `GitHubRateLimitError` | `GITHUB_RATE_LIMIT_UNKNOWN` | `1` | Git | Exception raised when GitHub rate limit quota state is broken or unknown and cannot be resolved. |
| `GitHubScopeError` | `GITHUB_SCOPE_MISSING` | `1` | Git | Raised when GitHub refuses a request because the token lacks a scope the endpoint needs. |
| `GitHubUnauthenticatedError` | `GITHUB_UNAUTHENTICATED` | `1` | Git | Raised when the process has no GitHub identity, or GitHub refused its token (HTTP 401). |
| `GitHubUnreadError` | `GITHUB_UNREAD` | `1` | Git | Raised when no answer from GitHub could be read, so what the request did is unknown. |
| `GitOperationError` | `GIT_OPERATION_ERROR` | `1` | Git | Base exception for Git repository and branch operation failures. |
| `GiteaAccessBlocked` | `GITEA_ACCESS_BLOCKED` | `1` | Gitea | Raised when Cloudflare Access blocks a Gitea request with a redirect or challenge. |
| `GiteaError` | `GITEA_ERROR` | `1` | Gitea | Base exception for Gitea forge operations. |
| `HTTPTimeoutTypeError` | `VALIDATION_ERROR` | `1` | Http | Raised when an invalid timeout parameter type is provided. |
| `HarnessValidationError` | `HARNESS_VALIDATION_ERROR` | `1` | Ai | Raised when an AI evaluation or harness schema validation fails. |
| `ImagePinError` | `K8S_IMAGE_PIN_ERROR` | `1` | K8s | Raised when an image that an Argo CD Application pins does not resolve in its registry, or an Application does not render (#1994). |
| `ImplementEvalError` | `ROADMAP_EVAL_REFUSED` | `1` | Roadmap | Raised when `devops roadmap eval implement` cannot read or use a fixture, or is asked for one that does not exist (#3030). |
| `InfraAccessRefusedError` | `INFRA_ACCESS_REFUSED` | `1` | Infra | An agent gave an agent access level above `none` for an infra repo. Only a person sets it. |
| `InfraApplyRefusedError` | `INFRA_APPLY_REFUSED` | `1` | Infra | A guard of `devops infra apply` refused the apply before it changed a host: the plan, its hash, age or arguments, the commit at origin, the host key checks, or the health of the cluster (#5125). |
| `InfraError` | `INFRA_ERROR` | `1` | Infra | Base exception of the infra repo commands. |
| `InfraNodeRefusedError` | `INFRA_NODE_REFUSED` | `1` | Infra | A guard of `devops infra node` refused the run before it changed a node: a host that is not in service in the inventory, a restart with no unit, `--force` from an agent, or host key checks off for an agent (#5128). |
| `InfraReadError` | `INFRA_READ_FAILED` | `1` | Infra | A read of an infra repo failed: a git command of the read of its default branch, an Ansible command, or its output is not JSON. |
| `InfraRepoNotFoundError` | `INFRA_REPO_NOT_FOUND` | `1` | Infra | The checkout of an infra repo is not where the settings or the arguments put it. |
| `InvalidBranchNameError` | `INVALID_BRANCH_NAME` | `1` | Git | Raised when a proposed Git branch name violates naming conventions. |
| `InvalidURLError` | `INVALID_URL` | `1` | Validation | Raised when an invalid URL or URI scheme is provided. |
| `InventoryError` | `RESEARCH_INVENTORY_ERROR` | `1` | Research | Raised when `devops research inventory` cannot read or parse a file that holds pins (#3896). |
| `KeyringUnavailableError` | `KEYRING_UNAVAILABLE` | `3` | Security | Raised when the OS Keyring service is unreachable or uninitialized. |
| `KubernetesContextError` | `K8S_CONTEXT_ERROR` | `1` | K8s | Raised when a Kubernetes context cannot be resolved or is invalid. |
| `KubernetesDeployError` | `K8S_DEPLOY_ERROR` | `1` | K8s | Raised when deploying manifests or Helm charts fails. |
| `KubernetesError` | `K8S_ERROR` | `1` | K8s | Base exception for Kubernetes operations. |
| `KubernetesLoggingError` | `K8S_LOGGING_ERROR` | `1` | K8s | Raised when querying cluster logs or Loki fails. |
| `KubernetesTunnelError` | `K8S_TUNNEL_ERROR` | `1` | K8s | Raised when `devops k8s tunnel` cannot start, find or stop its forward (#1641). |
| `LLMInferenceError` | `LLM_INFERENCE_ERROR` | `10` | Ai | Base exception for LLM provider invocation failures. |
| `LibraryIngestionError` | `LIBRARY_INGESTION_ERROR` | `1` | Ai | Base exception for package introspection and library ingestion errors. |
| `LibraryNotFoundError` | `LIBRARY_NOT_FOUND_ERROR` | `1` | Ai | Raised when target package could not be loaded or found in the environment. |
| `LimitReached` | `LIMIT_REACHED` | `15` | Ai | A step spent one of its budgets of tokens or time, so it makes no more model requests (#3053). The message names the setting and its value. |
| `LogfireConfigurationError` | `LOGFIRE_CONFIG_ERROR` | `1` | Telemetry | Raised when the Logfire bridge cannot start. |
| `MemoryProfilerError` | `PROFILER_ERROR` | `1` | Telemetry | Domain exception raised when memory profiling target resolution or execution fails. |
| `ModelBundleError` | `MODEL_BUNDLE_ERROR` | `1` | Ai | Raised when an AI model bundle cannot be located, resolved, or loaded. |
| `ModelGatewayUnreachableError` | `MODEL_GATEWAY_UNREACHABLE` | `1` | Ai | Raised when a model call through the gateway fails, so the command decided and wrote nothing. |
| `ModelRetry` | `MODEL_RETRY_REQUESTED` | `14` | Ai | Raised by tools or output validators to request the model to retry with corrective feedback. |
| `OtlpExportError` | `TELEMETRY_ERROR` | `1` | Telemetry | Raised when the collector does not take an OTLP export, with the failure as its message. |
| `OtlpProtocolError` | `TELEMETRY_ERROR` | `1` | Telemetry | Raised when the OTLP protocol or endpoint asks for gRPC, which devops-cli does not send. |
| `OutputCapReached` | `OUTPUT_CAP_REACHED` | `15` | Ai | A model reply ended with the finish reason `length`: the model did not stop, and the output cap ended the call (#2869). The message names the cap. The run drops a reply that a hook rejects, so the error holds it in `response`, for the spend. |
| `OverWindowError` | `ROADMAP_IMPLEMENT_REFUSED` | `1` | Roadmap | Raised when the inputs of an implement step measure more than the window allows (#3057). |
| `PageTextError` | `PAGE_TEXT_ERROR` | `1` | Ai | Raised when the Crawl4AI service returns no usable text for a page. |
| `PhaseOutputError` | `ROADMAP_IMPLEMENT_REFUSED` | `1` | Roadmap | Raised when `publish` cannot read an output of the agent phase as data: a link in its path, a file that is not a regular file, a file over its size limit, or text that is not the model of the file (#6601). |
| `PoolLoadError` | `DEVOPS_CLI_ERROR` | `1` | Ai | Prometheus could not answer a pool load query. |
| `PublishRefusedError` | `ROADMAP_IMPLEMENT_REFUSED` | `1` | Roadmap | Raised when `publish` refuses the patch of the agent phase before the push: git cannot apply it, or it adds or changes a link, a gitlink, `.gitmodules` or a workflow file that the plan does not name (#6601). The message names the reason and each path, masked. |
| `QdrantClientError` | `DEVOPS_CLI_ERROR` | `1` | Ai | Raised when an interaction with Qdrant fails. |
| `RagIngestError` | `RAG_INGEST_FAILED` | `1` | Ai | Raised when one or more repositories fail during RAG ingestion. |
| `RefusedPullReply` | `REFUSED_PULL_REPLY` | `1` | Roadmap | The pull request text broke form rules after one retry (#3599). |
| `RegistryReadError` | `DOCKER_REGISTRY_READ_ERROR` | `1` | Docker | Raised when an image registry gives no digest for a tag: no anonymous pull, or a reply with no digest. |
| `RegistryTagNotFoundError` | `DOCKER_REGISTRY_TAG_NOT_FOUND` | `1` | Docker | Raised when an image registry answers HTTP 404 for a tag: the tag is not there (yet). |
| `ReplyRejectedError` | `LLM_INFERENCE_ERROR` | `10` | Ai | Raised when the caller's validator refused a reply; it carries the reply, never cached. |
| `ResponseTooLargeError` | `RESPONSE_TOO_LARGE` | `1` | Security | Raised when the body of a response passes the byte cap of its client. |
| `ReviewHandOffRefusedError` | `REVIEW_HAND_OFF_REFUSED` | `1` | Ai | Raised when `devops review intake` refuses a session that is not on merged code. |
| `ReviewPoolError` | `REVIEW_POOL_ERROR` | `1` | Ai | Raised when an error occurs during parallel review worker pool execution. |
| `ReviewScannerMissingError` | `REVIEW_SCANNER_MISSING` | `1` | Ai | Raised when a review in the pod of a runner Job needs a scanner that its image lacks. |
| `ReviewSessionExistsError` | `REVIEW_SESSION_EXISTS` | `1` | Ai | Raised when a review is published under the name of a session that is already published. |
| `ReviewStateError` | `REVIEW_STATE_ERROR` | `1` | Review | Exception raised for invalid review finding state or state transition. |
| `RoadmapAlternativesError` | `ROADMAP_ALTERNATIVES_FAILED` | `1` | Roadmap | Raised after an alternatives run that tried items and checked none of them. |
| `RoadmapClaimError` | `ROADMAP_ITEM_CLAIMED` | `1` | Roadmap | Raised when a claim of a roadmap Item is refused, because another owner holds it or because the issue is no Item (#2910). |
| `RoadmapImplementError` | `ROADMAP_IMPLEMENT_REFUSED` | `1` | Roadmap | Raised when `devops roadmap implement` refuses to start a step, or cannot read its inputs. |
| `RoadmapIntakeError` | `ROADMAP_INTAKE_FAILED` | `1` | Roadmap | Raised after an intake round in which the writes failed for one or more candidates. |
| `RoadmapItemChangedError` | `ROADMAP_ITEM_CHANGED` | `1` | Roadmap | Raised before a job's field write that would revert a change made since it read the Item. |
| `RoadmapMcpUnavailableError` | `ROADMAP_MCP_UNAVAILABLE` | `1` | Roadmap | Raised when the MCP server is unavailable at job start (#3221). |
| `RoadmapOpenRefusedError` | `ROADMAP_OPEN_REFUSED` | `1` | Roadmap | Raised when devops roadmap step open refuses to open or update a pull request (#5020). |
| `RoadmapPlanReadBackError` | `ROADMAP_PLAN_READ_BACK_MISMATCH` | `1` | Roadmap | Raised when the plan reader cannot read back the rendered files of a plan, or reads facts that differ from the proposal (#5214). |
| `RoadmapPlanRewriteError` | `ROADMAP_PLAN_REWRITE_REFUSED` | `1` | Roadmap | Raised when `devops roadmap plan-recheck --confirm` refuses to write a rewritten plan (#3556). |
| `RoadmapPullReviewLimitError` | `ROADMAP_PULL_REVIEW_LIMIT` | `1` | Roadmap | Raised before the model call of the step `review` when its request is over the cap of new tokens of one review (#5969). |
| `RoadmapRecordMarkLostError` | `ROADMAP_RECORD_MARK_LOST` | `1` | Roadmap | Raised after a job record write when a mark remains missing after two rewrites (#4555). |
| `RoadmapRefineError` | `ROADMAP_REFINE_FAILED` | `1` | Roadmap | Raised after a refine run in which the model call failed for one or more items. |
| `RoadmapReviewError` | `ROADMAP_REVIEW_FAILED` | `1` | Roadmap | Raised when `devops roadmap review run` cannot resolve its window, read git or load a catalog. |
| `RoadmapRunError` | `DEVOPS_CLI_ERROR` | `1` | Roadmap | Raised when one or more roadmap jobs fail during execution. |
| `RoadmapStageDegenerateError` | `ROADMAP_STAGE_FAILED` | `1` | Roadmap | Raised for an item whose plan reply holds a placeholder in every text of the plan (#4204). |
| `RoadmapStageError` | `ROADMAP_STAGE_FAILED` | `1` | Roadmap | Raised after a stage run in which one or more items failed (#2654). |
| `RoadmapStatusLostError` | `ROADMAP_STATUS_LOST` | `1` | Roadmap | Raised after a Status write when the issue, read again, holds another Status (#5018). |
| `RoadmapTimeBudgetError` | `ROADMAP_TIME_BUDGET` | `1` | Roadmap | Raised before a model call of a step whose time budget is spent (#5363). |
| `RouteRefusedError` | `ONBOARD_ROUTE_REFUSED` | `1` | Github | A row asked for a write that no route of `ROUTES` holds. |
| `RouteWriteError` | `ONBOARD_WRITE_FAILED` | `1` | Github | A write of a route failed: the row that sent it fails, and the next run continues. |
| `RunIndexNotConfiguredError` | `DEVOPS_CLI_ERROR` | `1` | Ai | No shared run index is configured. |
| `SSHRegistrationError` | `GITHUB_OPERATION_FAILED` | `1` | Github | Raised when SSH/signing key registration on GitHub fails. |
| `SSRFBlockedError` | `SSRF_BLOCKED` | `2` | Security | Raised when an outbound HTTP request targets a private or forbidden network IP. |
| `SandboxError` | `SANDBOX_ERROR` | `1` | Sandbox | Base exception for workload sandbox lifecycle operations. |
| `SandboxNotFoundError` | `SANDBOX_NOT_FOUND_ERROR` | `1` | Sandbox | Raised when requested sandbox instance or container cannot be found. |
| `SandboxPortAllocationError` | `SANDBOX_PORT_ALLOCATION_ERROR` | `1` | Sandbox | Raised when host port allocation encounters collisions or range exhaustion. |
| `SandboxUnavailableError` | `SANDBOX_UNAVAILABLE_ERROR` | `1` | Sandbox | Raised when this host cannot start the sandbox of a review tool, so the tool does not run. |
| `SandboxValidationError` | `SANDBOX_VALIDATION_ERROR` | `1` | Sandbox | Raised when sandbox configuration or directory mount paths violate security boundaries. |
| `SearchFailed` | `WEB_SEARCH_FAILED` | `1` | Ai | Raised when no provider of a web search answered: each one failed, was skipped, or the deadline ended the search. |
| `SearchQueryRefused` | `WEB_SEARCH_QUERY_REFUSED` | `1` | Ai | Raised when the guard stops a web search query before any provider runs. The message names the rule and never holds the query. |
| `SecurityError` | `SECURITY_ERROR` | `1` | Security | Base exception for all security, policy, and egress violations. |
| `ServiceAddressError` | `K8S_ERROR` | `1` | K8s | Raised when a cluster service address cannot be resolved. |
| `ServiceNotReachableError` | `DEVOPS_CLI_ERROR` | `1` | K8s | A service cannot be reached from outside the cluster. |
| `ServiceProbeError` | `K8S_SERVICE_PROBE_ERROR` | `1` | K8s | Raised when `devops k8s crawl4ai-check` or `devops k8s searxng-check` cannot probe a service: the forward, the throwaway pod or the probe fails, or a check fails (#3894, #3929). |
| `ServiceRequestError` | `SERVICE_REQUEST_ERROR` | `1` | Http | Raised when a request to a cluster service fails after the attempts of its retry policy. |
| `ServiceStatusError` | `SERVICE_STATUS_ERROR` | `1` | Telemetry | Raised when querying upstream published service status fails. |
| `ServiceStoppingError` | `SERVICE_STOPPING` | `1` | Roadmap | Raised when a request ends because the Service is stopping (#2753). |
| `StackCredentialError` | `K8S_STACK_CREDENTIAL_ERROR` | `1` | K8s | Raised when a stack credential cannot be read, checked, minted, revoked or stored (#2156). |
| `StoreError` | `STORE_ERROR` | `1` | Store | Raised when an S3 content store operation fails or a store request is refused. |
| `StoreImmutablePathError` | `STORE_IMMUTABLE_PATH` | `1` | Store | Raised when publishing to an existing immutable store path without `--replace`. |
| `StructuredOutputSchemaError` | `STRUCTURED_OUTPUT_SCHEMA_INVALID` | `1` | Ai | Raised when a schema class is missing or invalid for structured LLM output generation. |
| `StructuredOutputValidationError` | `LLM_INFERENCE_ERROR` | `10` | Ai | Raised when the model answered, but no answer validated against the schema after retries. |
| `SubprocessError` | `SUBPROCESS_FAILED` | `1` | Tools | Raised when an external subprocess command exits with a non-zero code or fails execution. |
| `TFAccessRefusedError` | `TF_ACCESS_REFUSED` | `1` | Tf | An agent attempted apply, destroy, or state mutation without explicit `apply` access. |
| `TFBudgetError` | `TF_BUDGET_BELOW_FLOOR` | `1` | Tf | Remaining GitHub REST core quota is below the pre-plan safety floor. |
| `TFError` | `TF_ERROR` | `1` | Tf | Base exception for OpenTofu wrapper guard failures. |
| `TaskPromptNotFoundError` | `TASK_PROMPT_NOT_FOUND` | `1` | Ai | Raised when a prompt name is not a file of the `ai/tasks/` folder of the package. |
| `TelemetryError` | `TELEMETRY_ERROR` | `1` | Telemetry | Base exception for telemetry, tracing, and metric collection errors. |
| `TemplateRenderError` | `VALIDATION_ERROR` | `1` | Core | Raised when a template cannot be rendered into valid output. |
| `TokenCountError` | `TOKEN_COUNT_ERROR` | `10` | Ai | Raised when the tiktoken encoding is unavailable, so no exact token count exists. |
| `ToolDownloadError` | `TOOL_DOWNLOAD_ERROR` | `1` | Tools | Raised when an external tool download fails or is rejected. |
| `ToolExecutionError` | `TOOL_EXECUTION_ERROR` | `1` | Tools | Base exception for external developer tool and binary execution failures. |
| `ToolFailed` | `TOOL_FAILED` | `16` | Ai | Raised when a tool encounters an unrecoverable runtime failure without requesting model retry. |
| `TraceValidationError` | `VALIDATION_ERROR` | `1` | Telemetry | Raised when trace metadata or flags fail validation. |
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
| `WebSearchError` | `WEB_SEARCH_ERROR` | `1` | Ai | Base of the errors of `web_search`. A caller that cannot stop on a search catches it. |

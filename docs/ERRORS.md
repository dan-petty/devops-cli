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

| Error Code | Exit Code | Domain | Description |
|---|---|---|---|
| `LLM_INFERENCE_ERROR` | `10` | Devops_cli.ai.client.models | Raised when an AI provider request fails with a user-actionable message. |
| `AGENT_RUN_ERROR` | `20` | Ai | Raised when an error occurs during an agent run lifecycle. |
| `APPROVAL_REQUIRED` | `17` | Ai | Raised by a tool or validator when human approval is required to proceed. |
| `BRANCH_ALREADY_EXISTS` | `1` | Git | Raised when attempting to create a branch that already exists. |
| `BUDGET_EXCEEDED` | `1` | Devops_cli.ai.agents.spend | Raised when an agent execution exceeds defined token or financial spend limits. |
| `CALL_DEFERRED` | `18` | Ai | Raised by a tool when execution is deferred to an external worker or async system. |
| `CHAOS_EXECUTION_ERROR` | `1` | K8s | Raised when chaos engineering injection or validation fails. |
| `ChecksumMismatchError` | `1` | Tools | Raised when downloaded tool archive SHA-256 does not match expected checksum. |
| `CONCURRENCY_LIMIT_EXCEEDED` | `25` | Ai | Raised when the concurrency queue depth exceeds max_queued. |
| `CONFIGURATION_ERROR` | `1` | Config | Base exception for configuration loading, validation, and serialization errors. |
| `CONTENT_FILTER_TRIGGERED` | `19` | Ai | Raised when a model response is filtered or refused by upstream content safety filters. |
| `CONTEXT_BUDGET_EXCEEDED` | `11` | Ai | Raised when prompt token payload exceeds model context window limits. |
| `DEPENDENCY_MISSING` | `1` | Tools | Raised when a required external binary/dependency is missing from the system PATH. |
| `DOCKER_ERROR` | `1` | Docker | Base exception for Docker operations. |
| `DOCKER_SANDBOX_ERROR` | `1` | Docker | Raised when docker sandbox execution, container creation, or termination fails. |
| `GITHUB_OPERATION_FAILED` | `1` | Git | Exception raised for GitHub API or CLI automation failures. |
| `GIT_OPERATION_ERROR` | `1` | Git | Base exception for Git repository and branch operation failures. |
| `HARNESS_EXECUTION_ERROR` | `1` | Ai | Raised when execution of an AI test harness or benchmark fails. |
| `HARNESS_VALIDATION_ERROR` | `1` | Ai | Raised when an AI evaluation or harness schema validation fails. |
| `INCOMPLETE_TOOL_CALL` | `27` | Ai | Raised when a model stops due to token limit while emitting a tool call. |
| `E_INSECURE_CONFIG` | `126` | Security | Raised when an unencrypted plaintext secret token is found in configuration files. |
| `INVALID_BRANCH_NAME` | `1` | Git | Raised when a proposed Git branch name violates naming conventions. |
| `INVALID_URL` | `1` | Validation | Raised when an invalid URL or URI scheme is provided. |
| `INVALID_VERSION` | `1` | Validation | Raised when a semantic version string cannot be parsed. |
| `KEYRING_UNAVAILABLE` | `3` | Security | Raised when the OS Keyring service is unreachable or uninitialized. |
| `K8S_CONTEXT_ERROR` | `1` | K8s | Raised when a Kubernetes context cannot be resolved or is invalid. |
| `K8S_DEPLOY_ERROR` | `1` | K8s | Raised when deploying manifests or Helm charts fails. |
| `K8S_ERROR` | `1` | K8s | Base exception for Kubernetes operations. |
| `LLM_INFERENCE_ERROR` | `10` | Ai | Base exception for LLM provider invocation failures. |
| `MODEL_API_ERROR` | `22` | Ai | Raised when a model provider API request fails. |
| `MODEL_BUNDLE_ERROR` | `1` | Ai | Raised when an AI model bundle cannot be located, resolved, or loaded. |
| `MODEL_HTTP_ERROR` | `23` | Ai | Raised when a model provider response has a status code of 4xx or 5xx. |
| `MODEL_REQUESTS_DISABLED` | `1` | Devops_cli.ai.agents.testing | Raised when a non-test model request is attempted while ALLOW_MODEL_REQUESTS is False. |
| `MODEL_RETRY_REQUESTED` | `14` | Ai | Raised by tools or output validators to request the model to retry with corrective feedback. |
| `MODEL_UNAVAILABLE` | `12` | Ai | Raised when the requested LLM backend or model endpoint is unreachable. |
| `PERSONA_EXECUTION_ERROR` | `13` | Ai | Raised when an AI reviewer persona fails during diff analysis. |
| `RUN_CANCELLED` | `26` | Ai | Raised when an agent run was cancelled by the application or timeout. |
| `SSRF_BLOCKED` | `2` | Security | Raised when an outbound HTTP request targets a private or forbidden network IP. |
| `SecretExposureError` | `1` | Security | Raised when an unmasked credential or private key is detected in uncommitted diffs. |
| `SECURITY_ERROR` | `1` | Security | Base exception for all security, policy, and egress violations. |
| `SUBPROCESS_FAILED` | `1` | Tools | Raised when an external subprocess command exits with a non-zero code or fails execution. |
| `SUSPENDED_RESPONSE_EXPIRED` | `28` | Ai | Raised when resuming a suspended response whose server-side job is no longer available. |
| `ToolDownloadError` | `1` | Tools | Raised when an external tool download fails or is rejected. |
| `TOOL_EXECUTION_ERROR` | `1` | Tools | Base exception for external developer tool and binary execution failures. |
| `TOOL_FAILED` | `16` | Ai | Raised when a tool encounters an unrecoverable runtime failure without requesting model retry. |
| `UNEXPECTED_MODEL_BEHAVIOR` | `15` | Ai | Raised when model retry budget is exhausted or model emits unrecoverable response. |
| `USAGE_LIMIT_EXCEEDED` | `24` | Ai | Raised when an agent run exceeds configured request or token limits. |
| `USER_ERROR` | `21` | Ai | Raised when an invalid configuration or argument is provided by the application developer. |
| `VALIDATION_ERROR` | `1` | Validation | Base exception for user input and format validation failures. |
| `VAULT_CONFIGURATION_ERROR` | `1` | Vault | Raised when Vault environment or connection settings are missing or invalid. |
| `VAULT_ERROR` | `1` | Vault | Base exception for HashiCorp Vault operations. |
| `VAULT_KEY_ERROR` | `1` | Vault | Raised when a secret key or field is not found in Vault. |
| `VAULT_OPERATION_ERROR` | `1` | Vault | Raised when an API request to Vault fails or returns an error response. |

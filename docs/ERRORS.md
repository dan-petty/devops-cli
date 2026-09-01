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
| `APPROVAL_REQUIRED` | `17` | Ai | Raised by a tool or validator when human approval is required to proceed. |
| `BRANCH_ALREADY_EXISTS` | `1` | Git | Raised when attempting to create a branch that already exists. |
| `BUDGET_EXCEEDED` | `1` | Devops_cli.ai.agents.spend | Raised when an agent execution exceeds defined token or financial spend limits. |
| `CALL_DEFERRED` | `18` | Ai | Raised by a tool when execution is deferred to an external worker or async system. |
| `ChecksumMismatchError` | `1` | Tools | Raised when downloaded tool archive SHA-256 does not match expected checksum. |
| `CONFIGURATION_ERROR` | `1` | Config | Base exception for configuration loading, validation, and serialization errors. |
| `CONTENT_FILTER_TRIGGERED` | `19` | Ai | Raised when a model response is filtered or refused by upstream content safety filters. |
| `ContextBudgetExceededError` | `1` | Ai | Raised when prompt token payload exceeds model context window limits. |
| `GIT_OPERATION_ERROR` | `1` | Git | Base exception for Git repository and branch operation failures. |
| `E_INSECURE_CONFIG` | `126` | Security | Raised when an unencrypted plaintext secret token is found in configuration files. |
| `INVALID_BRANCH_NAME` | `1` | Git | Raised when a proposed Git branch name violates naming conventions. |
| `INVALID_URL` | `1` | Validation | Raised when an invalid URL or URI scheme is provided. |
| `INVALID_VERSION` | `1` | Validation | Raised when a semantic version string cannot be parsed. |
| `KEYRING_UNAVAILABLE` | `3` | Security | Raised when the OS Keyring service is unreachable or uninitialized. |
| `LLM_INFERENCE_ERROR` | `10` | Ai | Base exception for LLM provider invocation failures. |
| `MODEL_REQUESTS_DISABLED` | `1` | Devops_cli.ai.agents.testing | Raised when a non-test model request is attempted while ALLOW_MODEL_REQUESTS is False. |
| `MODEL_RETRY_REQUESTED` | `14` | Ai | Raised by tools or output validators to request the model to retry with corrective feedback. |
| `ModelUnavailableError` | `1` | Ai | Raised when the requested LLM backend or model endpoint is unreachable. |
| `PersonaExecutionError` | `1` | Ai | Raised when an AI reviewer persona fails during diff analysis. |
| `SSRF_BLOCKED` | `2` | Security | Raised when an outbound HTTP request targets a private or forbidden network IP. |
| `SecretExposureError` | `1` | Security | Raised when an unmasked credential or private key is detected in uncommitted diffs. |
| `SECURITY_ERROR` | `1` | Security | Base exception for all security, policy, and egress violations. |
| `ToolDownloadError` | `1` | Tools | Raised when an external tool download fails or is rejected. |
| `TOOL_EXECUTION_ERROR` | `1` | Tools | Base exception for external developer tool and binary execution failures. |
| `TOOL_FAILED` | `16` | Ai | Raised when a tool encounters an unrecoverable runtime failure without requesting model retry. |
| `UNEXPECTED_MODEL_BEHAVIOR` | `15` | Ai | Raised when model retry budget is exhausted or model emits unrecoverable response. |
| `VALIDATION_ERROR` | `1` | Validation | Base exception for user input and format validation failures. |

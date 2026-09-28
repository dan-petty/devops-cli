# Task 465: Missing or Rejected API Keys Named as Such

**Issue**: [#465](https://github.com/dan-petty/devops-cli/issues/465)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

With no API key configured (no `DEVOPS_CLI_AI_API_KEY` and no keyring entry), the
OpenAI-compatible client still sent `Authorization: Bearer ` with nothing after it. httpx
refuses that header value, so the request never left the machine. The user saw only "Provider
request failed. Check network access, API endpoint, and credentials." after four attempts, and
the server's logs showed nothing. This was observed with `devops ai chat` on `provider: gateway`
from a shell where the key had not been exported.

### Key Deliverables Completed:

- [x] **No Empty Bearer Token**: `_openai_compat_headers` sends `Authorization` only when a key
  is set, for chat, streaming and model listing. A server that needs no key works; one that does
  answers 401.
- [x] **Credentials Errors** (`AICredentialsError`, a subclass of `AIClientError`): a 401 or 403
  says whether the key is missing or was rejected, and names `DEVOPS_CLI_AI_API_KEY` and
  `devops config set ai.api_key`. Other HTTP failures keep their existing messages.
- [x] **No Retries on Credentials Failures**: `_retry_chat_dispatch` re-raises
  `AICredentialsError` at once instead of retrying.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_ai_client_credentials.py`: no `Authorization` header without a key (chat and
    model listing); missing, rejected and forbidden keys each fail once with the key's sources
    named; streaming reports a missing key.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

A gateway chat with no key configured failed after one request and 0.07 s with: "The gateway
provider requires an API key, but no API key is configured (HTTP 401). Set DEVOPS_CLI_AI_API_KEY
or run `devops config set ai.api_key`." The gateway logged the single 401.

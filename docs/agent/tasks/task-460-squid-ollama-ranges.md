# Task 460: Forward Ollama's Ranged Blob Requests Through Squid Unchanged

**Issue**: [#460](https://github.com/dan-petty/devops-cli/issues/460)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/k8s`, `priority/p1-high`

---

## 1. Description & Objectives

Ollama could not pull models through the Squid proxy. Pulls hung for hours and restarted
indefinitely. The gateway aliases that depend on those models (`devops-chat`, `devops-embedding`)
failed with `model not found`, so every gateway fallback chain ended in a broken tier.

Ollama downloads each blob from Cloudflare R2 as many parallel byte ranges. Squid ran
`range_offset_limit -1`, which answers every ranged request by fetching the whole object from
byte 0. Each range past the start waited for the full prefix, Ollama's stall detection aborted it,
and the pull restarted. In 54 minutes Squid logged 1,498 ranged `GET`s to R2. All of them were
`TCP_MISS_ABORTED`, and together they delivered 0 bytes.

Hugging Face downloads (vLLM weights) were unaffected because they are single-stream and start at
byte 0.

### Key Deliverables Completed:

- [x] **Scoped Range Handling**: `acl ollama_blob_storage dstdomain .r2.cloudflarestorage.com`
  with `range_offset_limit 0 ollama_blob_storage` ahead of the general `range_offset_limit -1`.
  Squid applies the first matching line, so ranged requests to Ollama's blob storage are
  forwarded unchanged, while other ranged requests still fetch the whole object and fill the
  cache. Partial responses are not cacheable, so Ollama blobs are not cached. They never were in
  practice, because none of those downloads ever completed.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_k8s_squid.py`: pins the ACL and the order of the `range_offset_limit` rules.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

After the ConfigMap was applied and Squid restarted, a `qwen2.5-coder:7b` pull logged 14 ranged
R2 requests. All of them were `TCP_MISS 206`, and they delivered 4.1 GB in the first minute. Before
the change, the same pull had hung for 90 minutes. `qwen2.5-coder:7b` (4.7 GB) and `bge-m3` then
pulled on both Ollama nodes in under three minutes. Through the gateway, `devops-chat` answers and
`devops-embedding` returns 1024-dimension vectors.

The gateway's health check still reports `devops-embedding` as unhealthy, because it probes the
model with a generate call. This is tracked separately.

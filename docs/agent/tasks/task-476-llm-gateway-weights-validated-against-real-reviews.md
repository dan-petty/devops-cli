# Task 476: LLM Gateway Weights Validated Against Real Reviews

**Issue**: [#476](https://github.com/dan-petty/devops-cli/issues/476)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

`devops ai gateway tune` (#470) recommends 3/5/1/2 for `devops-review` against the live 5/3/1/1
(dual-GPU vLLM 32B / single-GPU vLLM 14B / P6000 Ollama / V100-class Ollama), from review-sized
synthetic prompts. A sweep is not a review, so both configurations were compared on real reviews
before adopting either.

### Key Deliverables Completed:

- [x] **A/B on real reviews**: three iterations over the homelab playbooks (15 files,
  all personas, `--no-pre-analysis --no-cache`). Each iteration ran both configurations, with the
  order alternated between iterations (A→B, B→A, A→B). The weights actually loaded were confirmed
  through `/model/info` before every run.
- [x] **Decision**: keep 5/3/1/1. The tuned weights are faster, but they degrade findings on this
  corpus (see below). Verification moves to its own model task, so generation can take faster
  weights without weakening the check on findings: #486.

## 2. Results

| Config | Iteration 1 | Iteration 2 | Iteration 3 | Median | Seconds per candidate | Reported findings |
|---|---|---|---|---|---|---|
| A: 5/3/1/1 | 305 s | 229 s | 223 s | 229 s | 4.64 | 3, 7, 1 |
| B: 3/5/1/2 | 170 s | 185 s | 202 s | 185 s | 2.84 | 11, 6, 12 |

B was faster in every iteration: 19% on the median, 39% per candidate finding. Calls followed
the weights. Under A the split was 49% dual-GPU vLLM, 29% single-GPU vLLM and 21% Ollama; under B
it was 24%, 50% and 25%.

B also changed what the review reported. It produced more candidates (median 65 against 54) and
more reported findings, including top-severity false positives that passed verification:

- "Hardcoded Secrets" on registry-mirror URLs, which are not secrets. It was VERIFIED in one of
  its two appearances.
- "Unencrypted Communication Scheme" for plain HTTP to the in-cluster registry mirror, which is a
  deliberate LAN design. It is at most a low-severity note.

Under B, half of all calls (verification included) go to the 14B model, the most likely source.
Individual calls cannot be attributed to backends until #474 records the serving backend. Three
runs per configuration against one corpus measure a trade-off, not ground truth. The review
quality baseline (#475) is what can settle whether B's extra findings are noise.

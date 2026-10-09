# Review findings come from tools and checked facts; models explain and plan

`devops review` asked a model to find defects page by page, and a second model call to verify them. On a fixed input the result was a sample, not a measurement. Ten `--no-cache` runs of release/v0.2.25 at e3ff98c (S12–S21) reported 28–57 findings each and 154 distinct findings in all. Two runs agreed on persona findings with a mean Jaccard of 0.131. One run found 38% of the nine known valid defects. None of the 94 VERIFIED rows and none of the 50 HIGH or CRITICAL rows was strictly valid. A file that does not exist, `app/shell.py:4`, was VERIFIED and ranked first in all eleven runs, S11 included. The model called Python 3.14's unparenthesized `except A, B:` a syntax error 22 times, and the verifier confirmed it 3 times. The scanner candidates were identical in every run, and every strictly valid row was a kube-linter result. The model verifier refuted all 90 read-only-root-filesystem results; 49 were kept only because a guard blocked those refutations. Voting over five runs raised lenient precision only from 17.4% to 25.2%, at five times the calls. Each failure had been answered with another guard or catalog entry: the catalog holds 53 hand-kept entries, and `verification.py` changed in 20 commits in one month.

The knowledge base and the document ingestors never reached a review. On 2026-09-30 a search that hit a vector-dimension mismatch deleted and recreated both Qdrant collections, and nothing has written to them since. All 2,084 searches in the loop returned nothing. No command, schedule or hook runs ingestion. Drift is measured against a local cache, not the index, so the wipe looked like no drift. The docs ingestor writes files nothing reads. Contract grounding found a contract in 0 of 20,244 file payloads. The review queried its own code index by file path and symbol names, never by what a finding names. The knowledge base states PEP 758 correctly, but it carries no version metadata, and 7 of the 25 versions it states differ from the lockfile.

A finding now exists only when one of these produces it:
- a pinned tool, including the language's own compiler and type checker at the project's declared floor;
- an advisory database;
- a language or dependency fact confirmed at the declared and locked versions;
- a rule in devops-cli's tested rule pack, where reference-exploit rules join only when a person merges them;
- (later) a replayed sandbox observation.

One admission function builds every finding from that anchor. It checks that the location exists in the reviewed commit: a line region, or the named object or package when the tool reports no line. It takes severity from the rule's metadata and a policy table. Only tools and people change a finding's state:
- a tool run opens or fixes it;
- reviewed project configuration suppresses it;
- a person's valid verdict or a replayed observation confirms it.

Tools run on a worktree of the reviewed commit, inside the sandbox with no network, at the language and dependency versions the project declares. Inline suppression markers count only where they already exist at the base revision. A tool's findings count only after its output on a canary for the target language version matches the recorded expected output.

A reference store of version-pinned facts and official documentation sits beside the tools:
- **Contents:** derived from the reviewed project (its languages, version floor, locked dependencies, tools and the rules that fired), plus the project's own knowledge-base manuals where the versions they state match.
- **Refresh:** a side effect of running devops commands. Fetches that could not finish wait in a pending list that later commands drain.
- **Lookup:** by key, with a full-text fallback.
- **Reporting:** every review reports what it needed, what each model job received and what was missing.

Models correlate, explain and plan from findings and reference items. Their output is stored apart from findings, and it has no field that can create, move, re-rate or change the state of a finding. Its quotes, citations, version strings and code are checked before they are shown.

A patch counts only when both of these pass on the patched tree in the sandbox:
- the producing tools, with inline suppressions ignored;
- the base revision's mapped tests.

A patch that changes a suppression, a test or tool configuration does not count.

Review work runs as content-addressed jobs pulled by one worker per GPU tier slot, so no tier idles while the queue holds work it can serve.

## Considered Options

- **Keep model-generated findings and harden verification** (more guards, self-consistency voting, better prompts): rejected. Voting cannot remove deterministic false positives: 22 false clusters survived a majority vote. On kube-linter rows the guards kept false findings more often than valid ones (153/200 against 49/90). More prompt and guard fixes are what the last month's churn already was.
- **Fix ingestion and keep page-level embedding search as the review's knowledge path**: rejected. The query names a file, not a fact; code embeddings track identifier names; and the stored text had no version. A keyed lookup with a full-text fallback is still retrieval for generation, but it needs no vector store. Embeddings stay for chat and the knowledge base's index, and may return to reviews once labelled misses show that keyed and full-text lookups miss relevant documents.
- **Let model-written reference-exploit rules produce findings once their tests pass**: rejected. A rule written after seeing the candidate, and tested on it, proves only that it matches what it was fitted to. Such a rule passed `semgrep --test` on a safe candidate. Model-written rules produce leads until a person merges them into the pack.
- **Route through the gateway alone** (least-busy, `max_parallel_requests`) as the scheduler: rejected for the job system. It cannot see that the 48gib-slow tier's two models share one slot, its 429s put a deployment into cooldown, and it keeps no record per item. Until the job system exists, the current pipeline uses least-busy behind a client cap. `cancel_on_disconnect` and `num_retries: 0` stay as safety nets.
- **Target workers at a LiteLLM deployment id**: rejected while BerriAI/litellm#43495 is open. Each tier gets a one-deployment model group instead.
- **A cluster-side queue (Kubernetes Jobs) or DBOS for every item**: rejected. A pod per 3–18 s call costs more than the call, and DBOS fixes a job's partition when it is enqueued and adds three dependencies. Kubernetes Jobs remain the executor for sandboxed probes.
- **Vendoring Semgrep registry rules or bundling the CodeQL CLI**: rejected by their licences. This repository is public, so anything committed is redistributed. Registry rules are fetched into the user's own cache for internal use, and CodeQL results are read from GitHub code scanning.

## Consequences

- **Deleted, not kept behind flags (pre-1.0):** the persona review stage, the model verifier, the hallucination catalog, the model-claim guards and the legacy segment engine. The persona definitions stay for chat and analysis.
- **A false positive is fixed once:** in tool configuration, or as a suppression with a reason and an expiry. A missed defect becomes a tested rule in devops-cli's rule pack. Nothing records model mistakes any more.
- **Out of scope until someone writes a rule:** defects that no tool or rule can express, such as a prose claim in VISION.md or a missing depth limit.
- **The pinned tools become part of the supply chain.** A tools lock with checksums and hashed requirements, the sandbox and the canary guard them, and each review lists newer releases of every pinned tool.
- **Stability is defined over equal inputs:** the commit, the tools lock, the ruleset snapshot, the advisory database snapshot and the reference store snapshot.
- **The knowledge base's manuals declare the versions they apply to.** Matching manuals ground explanations; mismatched ones are reported as drift. Chat's index of the knowledge base is rebuilt whenever the installed knowledge base differs from what the index holds.
- **`devops ai ingest` becomes `status`, `sync`, `lookup` and `prune`** over the reference store. Its `library`, `docs`, `index-libraries` and `query-library` commands go.
- **Documentation changes:**
  - CONTEXT.md's code-review terms change, and VISION.md items 8 and 16 change;
  - README.md, AGENTS.md section 5, SELF_IMPROVEMENT.md, KNOWN_ISSUES.md and TELEMETRY.md are rewritten through their usual paths;
  - the findings metric's `persona` label becomes `producer`.

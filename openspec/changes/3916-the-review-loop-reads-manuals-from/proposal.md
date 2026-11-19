# Proposal

## Why

The review is the only place where a manual enters a model prompt by key, and it reads front-matter articles that type a version in the text, so a version change drops an article as drift and the report never says which source grounded the analysis. Item #3916 moves that source to the index, where a record carries the source URL, the fetch date, the content hash, the expiry and a version range, the version comes from the lock files at read time, and the key names what grounded the analysis.

## What Changes

- `src/devops_cli/ai/kb.py` reads the review manuals from the research collection and no longer scans the front-matter articles.
- `src/devops_cli/ai/kb.py` adds `ManualIndexRecord`, `read_manual_index_records` and `manual_reference_key`, and drops the `kb_dir` argument of `load_matched_kb_manuals`.
- `read_manual_index_records` takes its client from `src/devops_cli/ai/rag/indexer.py:def resolve_qdrant_client`, so the `qdrant` fixture serves every case and no case builds `src/devops_cli/ai/rag/qdrant.py:class QdrantClient`.
- `src/devops_cli/ai/kb.py` keeps a record only when its version range contains the version of its component in the lock files at read time, and lists an expired record, a record refused at ingest and a mismatched record in the drift list with its reason.
- `src/devops_cli/ai/kb.py` returns no manual and one drift entry that names the unset `qdrant.url` setting, or one drift entry for an unreachable store, so a review with no store still renders its report and builds no client.
- `tests/review/test_review_group_analysis.py` and `tests/review/test_review_prompt_adversaries.py` pass `kb_manuals={}` at each `run_group_analysis` call site, so no case of those modules reads the store.
- `tests/review/test_kb_manuals_metadata.py` loads records into the `qdrant` fixture and asserts a returned manual, a drift reason and a key.
- `tests/review/test_report.py` asserts that the report shows an expired record and a record refused at ingest beside version drift.
- `src/devops_cli/ai/kb.py` deletes the front-matter matchers that only the article scan called.
- `ARCHITECTURE.md` states that a review reads its manuals from the research index and reports an expired, refused or unread record, and `docs/SELF_IMPROVEMENT.md` records the before-and-after score protocol and the two score tables.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `review-manual-index`: A manual is returned only at the pinned version, An expired record is not returned and is reported as expired, A record refused at ingest is reported, The key of a returned manual names its URL, date and hash, A manual index that the review cannot read is a reported gap

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/kb.py`
- Documents: `ARCHITECTURE.md`, `docs/SELF_IMPROVEMENT.md`
- Tests: `tests/review/test_kb_manuals_metadata.py`, `tests/review/test_review_group_analysis.py`, `tests/review/test_review_prompt_adversaries.py`, `tests/review/test_report.py`

## Feasibility

- The probes confirm the cited paths word for word: "The path `uv.lock` is a file of the staging commit." and "The path `src/devops_cli/ai/rag/__init__.py` is a file of the staging commit." and "The path `docs/adr/0005-review-findings-come-from-tools-not-models.md` is a file of the staging commit." and "The path `tests/review/test_kb_manuals_metadata.py` is a file of the staging commit."
- The probes place the tools lock away from the root: "The path `tools.lock` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/tools_lock/tools.lock`, `tests/fixtures/research/repo/src/devops_cli/tools_lock/tools.lock`. No commit in the history deleted or renamed it." The plan reads the tool versions from the tools lock object and from the `environment` facts that the caller passes.
- `read_file` on `src/devops_cli/ai/kb.py` lines 580 to 669 confirmed the premise of the issue: `src/devops_cli/ai/kb.py:629:def load_matched_kb_manuals(` walks `src/devops_cli/ai/kb.py:656:for sub in CONST_KB_METADATA_TARGET_SUBDIRS:`, so the review reads articles and no index.
- The finding of the model review was correct, and `read_file` on `src/devops_cli/review/analysis.py` lines 1480 to 1530 shows why: `src/devops_cli/review/analysis.py:1510:if kb_manuals is None:` and `src/devops_cli/review/analysis.py:1511:matched_kb, discovered_drift = load_matched_kb_manuals(environment=eff_env)`, so a case that calls `run_group_analysis` with no `kb_manuals` reaches the loader.
- `search_code` for `run_group_analysis` lists those cases: `tests/review/test_review_group_analysis.py:551:report = run_group_analysis(` and `tests/review/test_review_prompt_adversaries.py:375:plan_report = run_group_analysis(`, beside eight call sites of the first module, none of which passes `kb_manuals`. Group 1 changes both modules and passes `kb_manuals={}` at each call site, so no case of them reaches the loader or the store.
- `src/devops_cli/ai/review/pipeline.py:3173:else tuple(load_matched_kb_manuals(kubernetes_version=self.kubernetes_version)[1])` is the report path, and it has no manual seam, so the loader reports a gap instead of building a client: `src/devops_cli/ai/rag/indexer.py:459:override = get_qdrant_client_override()` returns an installed fake first, and with no override `src/devops_cli/ai/rag/indexer.py:469:"No Qdrant vector store URL configured. Run: devops config set qdrant.url <url>",` raises before any socket.
- `docs/TESTING.md:121:The fixture writes the overrides into the test's own` shows that a case writes its own configuration, so a case has no `qdrant.url` and the gap path is the one it takes; no case sends a request.
- The key keeps the staged constants: `src/devops_cli/config/constants.py:5573:CONST_KB_SHA_DIGEST_LENGTH: Final[int] = 16` gives the 16 characters, and `src/devops_cli/ai/kb.py:614:sha = hashlib.sha256(content.encode("utf-8")).hexdigest()[:CONST_KB_SHA_DIGEST_LENGTH]` gives the hash prefix of the key.
- `src/devops_cli/ai/kb.py:233:class DriftManual(BaseModel):` carries a path and `src/devops_cli/ai/kb.py:239:reason: str`, so an expired, a refused and a gap entry reuse the field that the report renders.
- The article count is the one the test pins, `tests/review/test_kb_manuals_metadata.py:71:assert len(target_articles) == 59`; the count of 11 dropped articles is not checked by this run.
- Precondition of `src/devops_cli/ai/rag/indexer.py:def resolve_qdrant_client`: it needs a client of the Qdrant service, or the override that `src/devops_cli/ai/rag/qdrant.py:382:def install_qdrant_client(override: QdrantProtocol | None) -> None:` installs; the `qdrant` fixture installs it at `tests/support/fakes/qdrant.py:539:install_qdrant_client(fake)`, so a case of group 1 reads memory and opens no socket.
- Precondition of the record read: `tests/support/fakes/qdrant.py:210:def scroll_points(` needs the client of the fake that `tests/support/fakes/qdrant.py:534:def qdrant() -> Iterator[Any]:` installs, and its refusal path is `tests/support/fakes/qdrant.py:220:raise QdrantClientError("Server is unreachable")`, which the gap case asserts.
- Precondition of `src/devops_cli/ai/kb.py:def _lookup_uv_lock_version`: it reads the `uv.lock` of the current folder, so a caller that passes no version needs a checkout of the repository; each case passes its versions in.
- Precondition of the tools lock load: it reads `src/devops_cli/tools_lock/tools.lock`, which needs a checkout of the repository or the installed package; each case passes the lock object in.
- Precondition of `src/devops_cli/commands/review.py:def review_score`: it reads the session folders and the label file that the caller names, so it needs a checkout of the repository, no client and no network.
- `uv run devops ci test tests/review/test_kb_manuals_metadata.py` and `uv run devops ci test tests/review/test_report.py` run `pytest`, which the runner image holds; their failure class is `test`, and the pod runs them with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false` and `capabilities.drop: ALL`.
- `search_code` for `_evaluate_applies_to` gave 2 hits, `src/devops_cli/ai/kb.py:436:def _evaluate_applies_to(` and `src/devops_cli/ai/kb.py:602:is_match, reason = _evaluate_applies_to(`, both in `src/devops_cli/ai/kb.py`, so the verify `! git grep -n -I -F -w _evaluate_applies_to src/ tests/` passes once group 3 deletes them; it runs `git`, which the runner image holds, and its failure class is `lint`.
- `search_code` for `_process_manual_file` gave 2 hits, `src/devops_cli/ai/kb.py:587:def _process_manual_file(` and `src/devops_cli/ai/kb.py:663:item, drift_item = _process_manual_file(md_file, base_dir, ctx)`, and `search_code` for `_extract_manual_tags` gave 2 hits, `src/devops_cli/ai/kb.py:460:def _extract_manual_tags(` and `src/devops_cli/ai/kb.py:616:tools, topics, tags = _extract_manual_tags(rel_path, fm)`, so that whole chain is reachable only from the article scan and goes with it.
- `search_code` for `_version_matches_pattern` gave 4 hits, `src/devops_cli/ai/kb.py:295:def _version_matches_pattern(ver: str, pattern: str) -> bool:` and three calls inside the matchers, so group 1 keeps it and calls it from the record match.
- `uv run devops review score` runs `devops`, which the runner image holds, and its failure class is `test`; `uv run devops review path` needs `semgrep` and `osv-scanner`, both `NOT_IN_RUNNER`, and a network to the model gateway, so no runner verify runs it and group 4 records it as a person's process on a workstation.
- not checked: the manual record payload, its version range, its refusal mark and the collection name that the research store of #3906 writes, because no module of this commit writes or reads that payload; the dependency entry puts #3906 first.

## Existing Tool Considered

Qdrant with `qdrant-client` is the open, maintained store that `uv.lock` already locks and that the existing indexer writes; `packaging` is already locked and covers the version range. The project builds a thin read adapter and the drift reasons, at about 25k tokens and 3 hours to build, keep and fix. The change deletes the front-matter scan of `load_matched_kb_manuals`, `_process_manual_file`, `_evaluate_applies_to`, the `_match_*` helpers and `_extract_manual_tags`.

## Dependencies

- #3906: The research store and the collection that holds the manual records are not in this tree, and the review lookup reads the records that #3906 writes, so #3906 merges first.

## Friction

One Valkey error turns the L2 cache off for the rest of the run: `self._valkey = None` in `src/devops_cli/ai/rag/embeddings.py` (two places) and `src/devops_cli/security/vulnerability_lookup.py` (three places). `cache/tiered.py` does the opposite and retries and reconnects on every call during an outage. Neither has a cooldown or a half-open state, and the RAG lookup pause has its own hand-written breaker.

## Evidence

Checked on main on 2026-10-24: the five `self._valkey = None` lines are present, and no circuit breaker library is a dependency. This is PR2 of tracking issue #596.

## Proposed remedy

- Adopt one maintained circuit breaker library (for example pybreaker; check its maintenance first) behind one seam at the Valkey L2 boundary, with open, cooldown, half-open and closed states.
- Route the embeddings engine, the threat-intel client and `TieredCache` through it, and delete every `self._valkey = None`.
- Rewrite the test that pins the nulling so that it covers all four states.


Source: https://github.com/dan-petty/devops-cli/issues/596

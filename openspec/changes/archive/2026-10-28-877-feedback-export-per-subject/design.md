# Design

## Context

A review session saves its findings in `findings.json` and `candidates.json`. Since #871 and #1151, every finding comes from admission, which gives it a fingerprint v2 (`SavedFinding.fingerprint`). Since #607, a session records its subject, and review history ranks the sessions of one subject (`ReviewSessionRecord.rank`: a person's verdicts, then the judged findings, then the newest).

## Decisions

### One copy of each finding of a subject

The export reads every session, and keeps one copy of each finding. The key of a finding is its group and its fingerprint v2. The group is the subject key, or the session id when the session records no subject. A finding without a fingerprint v2 has the key it had before: its session, producer, location and title.

The copy that the export keeps is the highest of this order:

1. A person's verdict (`verified_by == "human"`) comes before every other verdict.
2. Of two human verdicts, the newer `verified_at` comes first.
3. Then the copy of the session with the higher history rank. The session that history counts for the subject has the highest rank, so its copy comes first among the copies that no person judged.

The copies of one finding in `findings.json` and `candidates.json` of one session have equal verdicts, so the first copy read, from `findings.json`, is kept.

### The filter reads the kept verdict

`--status` applies after the export keeps a copy. A person who invalidated a finding and later verified it in another session has a VERIFIED finding, and the default export of INVALIDATED verdicts does not export it.

### The dataset identity

`feedback_fingerprint` gives a record with a fingerprint v2 the identity (group, fingerprint v2, status, labeller). A later session of an exported subject with the same verdicts adds nothing, and a person's later verdict adds one record. A record without a fingerprint v2 keeps the per-session identity, which is also the identity of every record that an export wrote before this change.

## Rejected Alternatives

- **Export only the counted session of each subject, and add the human verdicts of the other sessions to it** (the issue's first design). Rejected: a finding that only another session of the subject holds is then lost unless a person judged it. Since #1151 the findings come from pinned tools, so a finding of another session is a real finding, not model noise. A union by fingerprint v2 keeps it once.
- **Match findings with `_are_findings_duplicate` or by title.** Rejected by the issue's 2026-10-08 update and #1137: fingerprint v2 (#1141) is the identity of a finding. A title match also joins two findings of one rule at different places.
- **Order human verdicts by session time.** Rejected: a person can judge an older session after a newer one. `verified_at` is the time of the verdict.
- **Add the per-session identity of each new record to the dataset check, so that records an earlier export wrote are never written again under the new identity.** Rejected: that is a transition rule. Pre-1.0, an export after this change can append one record again for a finding that an earlier export wrote with its session id.
- **Set CONFIRMED in the export record.** Rejected: no reader uses a state in the dataset, and the state belongs to the session's findings. #2414 decides where the state is stored.

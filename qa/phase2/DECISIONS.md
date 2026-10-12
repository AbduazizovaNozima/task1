# Phase 2 decision log

- User approved fixes in order; session/context deletion is the only pending product decision. QA-02 must wait.
- QA-03: XML parsing errors are mapped through both load and lazy iteration; two failures reproduced before change.
- QA-09: wait for storage readiness before ingestion, bounded by a 60-second retry deadline plus the configured duration of an in-flight request.
- QA-04: SQL transaction encloses all writes and vector upserts. SQL rollback occurs on any embedding/vector failure. PostgreSQL is the publication source; leftover vector entries after partial failure cannot publish absent SQL rows, and committed SQL answer identity overrides stale vector metadata. No outbox/queue.
- QA-05..08: deliver complete plain-text chunks, truthful reset errors, invalid upstream decoding mapped to API failure, and 422 classified as input validation.
- QA-10: every legacy query stays development data because it has already informed tuning. New holdout: 80 paraphrases covering 40 previously unevaluated answer IDs + 40 OOD. Frozen hash/provenance: eval/holdout_manifest.json. Duplicate service-information sources were explicitly accepted as equivalent before any scoring.
- QA-01: only global threshold calibration attempted. Dev objective and acceptance metrics were committed to frozen_candidate.json before holdout scoring. One candidate, 0.67, compared against 0.64. Aggregate holdout metrics all nondecreasing; 5 decisions improved, 0 worsened. Accept 0.67, without per-query holdout error inspection or additional candidate tuning. Residual wrong acceptances remain a known limitation.

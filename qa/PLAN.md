# Phase 1 adversarial QA plan
Scope: committed HEAD clean clone plus current working tree (record differences); application code is read-only.
1. Clone HEAD into qa/clean-clone. Execute README setup and clean Compose build, with isolated project/volumes/images; first demonstrate occupied ports, then use a QA override for free ports. Do not launch a real Telegram polling bot or send external messages.
2. Capture clean install, ruff, mypy, pytest, startup and health evidence.
3. Exercise real HTTP /ask, /ingest, /sessions and /health: malformed payloads, Unicode, nulls, limits, corrupted workbooks; isolate all ingestion writes.
4. Stop isolated PostgreSQL and Qdrant, exercise errors and recovery; restart and down/up persistence.
5. Run 20 concurrent requests, 50 sequential requests; sample resource use and health responsiveness.
6. Replay correctness examples and evaluation; inspect tuning leakage and existing assertions.
7. Add failing regression tests, write QA_REPORT.md with verified vs suspected results and explicit limitations. Stop for approval before fixes.

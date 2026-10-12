# Phase 1 adversarial QA report — task1_semantic_qa

Date: 2026-10-11. Verdict: **NOT READY**. Phase 1 only; no application fixes were made.

## 1. Summary and scope

**10 VERIFIED findings: 3 Critical, 3 High, 4 Medium, 0 Low.** No unverified suspicions are counted as findings. Critical includes a wrong answer asserted as correct, violation of the promised verbatim answer, and startup failure under delayed dependency readiness, following the requested severity definitions.

Target: `/home/nozima/Music/task1_semantic_qa`, committed HEAD `e8d9d06f7f17686562d8b58608779e85e37e5c22`, plus the existing working tree. Pre-existing changes include `bot/main.py`, Compose restart policy, ignore files, and deleted CSV/evaluation artifacts; see [initial status](evidence/original_status.txt). These were preserved. No task-specific checklist was supplied: its placeholder was still present. Requirements below are therefore derived from README, EVALUATION.md and the requested A–F checks.

Isolation: fresh `git clone --no-hardlinks . qa/clean-clone`; Compose project `task1_adversarial_qa`, separate volumes, model download, image `task1-adversarial-qa`, and ports 18000/15440/16333. Existing production/demo services on 8000/5440/6333 were not stopped. Initial non-writing probes used port 8000; core failures were repeated against the clean image on 18000. Bot handlers were exercised with captured outgoing messages; no Telegram messages were sent.

Important results:

- Clean application and bot Docker images built with `--no-cache` in **128.48 seconds**. Port collision was reported explicitly; rerunning with isolated ports succeeded. Cold Compose startup took **394.73 seconds**, including fresh model download and indexing 3,048 questions / 505 answers. This is time until Compose started the API, not a claim that its model warm-up was already complete. First measured request after readiness: **200, 0.252 seconds**.
- Existing working-tree and clean-clone suites each passed **83 tests** using the pre-existing Python environment. Their lint/type checks passed. Fresh-environment results are recorded below separately.
- **20/20 concurrent** and **50/50 sequential** requests returned 200; slowest concurrent request 2.094 seconds. `/health` during load: 200 in 0.279 seconds. API memory: 1.506 → 1.527 GiB; `/tmp` file count: 1 → 1. This short sample does not establish long-term leak freedom.
- PostgreSQL/Qdrant outages produced friendly 503 responses and recovered without an API restart. API restart and Compose down/up without `-v` retained data and conversation context. Import during a vector-store outage did **not** retain consistency (QA-04).
- Published evaluation figures reproduced to their displayed precision. A separate HTTP replay of all 245 questions produced **198 correct decisions, 34 accepted answers outside the annotated expected set, 13 in-domain rejections, zero HTTP errors**. Some annotation mismatches can be equivalent corpus answers; QA-01 uses unambiguously irrelevant examples, not an assumption that all 34 are semantically wrong.

## 2. Findings

Commands below run from the project root. For HTTP regression tests, use:

```bash
QA_API_URL=http://127.0.0.1:18000 .venv/bin/python -m pytest qa/test_regressions.py -q
```

This suite intentionally fails until fixes are approved. The test names in the table can be selected using `-k NAME` appended to that command. Fixtures and raw output are retained under `qa/`.

| ID | Severity | Area | Status | Exact reproduction / failing test | Expected | Actual and evidence | Likely cause (file:line) | Suggested fix |
|---|---|---|---|---|---|---|---|---|
| QA-01 | Critical | Semantic correctness | VERIFIED | POST `/ask` with `{"question":"pensiya nechpul"}` or `{"question":"ID-karta narxi"}`; `-k unrelated_answer` | Answer the requested amount/price, or abstain/clarify. | Pension amount returns payment method, `found=true`, score **0.6621781**. ID-card price returns personal fields printed/stored on the card, `found=true`, score **0.77538973**. [HTTP evidence](evidence/read_api.jsonl), [clean-image regressions](evidence/isolated_regressions.log). | `app/services/search.py:61`: best score crossing a global threshold is accepted; ambiguity only protects short near-ties. `app/services/conversation.py:38` also selects context by similarity, not requested intent. | Add targeted intent/answer relevance validation and abstain when amount/document requirements are unsupported; calibrate on a separate split. Do not simply lower the global threshold. |
| QA-02 | High | API text/session validation | VERIFIED | POST `/ask` with `{"question":"ID karta olish uchun nima kerak?","session_id":"qa\u0000null"}`; also put null at the end of a matched question with a nonempty session; DELETE `/sessions/qa%00null`. `-k 'null_bytes or null_session'` | 422 validation response; server remains usable. | **500 `Internal Server Error`**. Server traceback: `psycopg.DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes`. [Tracebacks](evidence/live_api_tracebacks.log), [DELETE evidence](evidence/more_inputs.json). | `app/api/schemas.py:5`, `app/api/routes.py:37`; length-only validation lets NUL reach SQL. `app/adapters/pg_connection.py:17` handles availability exceptions, not invalid text. | Reject NUL/control data consistently in request and path validation, before history reads/writes. |
| QA-03 | High | Excel upload validation | VERIFIED | `curl -i -F file=@qa/fixtures/malformed-xml.xlsx http://127.0.0.1:18000/ingest`; also `malformed-sheet.xlsx`; `-k corrupt_xml` | 422 explaining that the workbook is malformed. | Both return **500 `Internal Server Error`**; `xml.etree.ElementTree.ParseError: unclosed token: line 1, column 0`. Plain renamed text and zero-byte files correctly return 422. [Uploads](evidence/uploads.jsonl), [tracebacks](evidence/live_api_tracebacks.log). | `app/adapters/excel_reader.py:21`: incomplete exception mapping; errors during lazy worksheet iteration at line 28 are outside the load exception handler. | Map malformed-workbook/parser errors across both workbook load and row iteration to `InvalidSpreadsheetError`; retain cleanup. |
| QA-04 | High | Import atomicity / dependency failure | VERIFIED | `.venv/bin/python qa/exercise_isolated.py`: import `QA audit unique passport procedure` → `QA original answer`; stop QA Qdrant; import same question → `QA changed despite failure`; restart Qdrant and ask exact question. `-k failed_ingest` is the fast deterministic regression. | An unsuccessful import must not publish a replacement answer, or must explicitly report a resumable partial commit. | Import returns **503**; afterward `/ask` returns **200, `found=true`, `answer="QA changed despite failure"`, score 1.0**. SQL answer changed while the vector retained its previous answer ID. [Real API sequence](evidence/isolated_exercise.jsonl). | `app/services/ingestion.py:28`: SQL commit precedes vector lookup/upsert; no staging/rollback or publication boundary. | Stage imports and publish only after both stores agree, or implement recoverable transactional/outbox state; verify returned metadata and SQL answer correspond. |
| QA-05 | Critical | Bot answer preservation | VERIFIED | `-k bot_preserves_full_answer`: feed the actual question handler an API answer of 4,096 `x` characters plus ` MUHIM ISTISNO`; capture all outgoing message bodies. | Full source answer delivered, split into allowed message sizes if necessary. | Only the first **4,096 characters** are emitted; the final exception/qualification disappears without notice. This violates README's verbatim-answer promise. [Regression output](evidence/isolated_regressions.log). | `bot/main.py:35` slices the answer; `tests/test_bot.py:34` currently **asserts that truncation happens**, protecting the defect. | Split long answers into sequential messages without losing characters; test concatenated sent content against the entire source answer. |
| QA-06 | Medium | Bot reset / outage UX | VERIFIED | `PYTHONPATH=. .venv/bin/python qa/probe_bot_outage.py` stops only the QA API and invokes `/new` handler with real HTTP transport; `-k failed_reset` provides a fast mock regression. | State reset failure is clearly reported; success is shown only after reset succeeds. | `/new` still emits **`Yangi suhbat boshlandi. Savolingizni yozing.`** although API is unreachable and history has not been cleared. Ordinary questions correctly get the service-down message. [Actual outage](evidence/bot_actual_outage.json). | `bot/main.py:71–76`: exception logged and ignored, then unconditional success message. | Return a retryable reset-failure message from the error branch, and do not claim a new conversation. |
| QA-07 | Medium | Bot malformed upstream response | VERIFIED | `-k bot_wraps_invalid_upstream_responses`: inject HTTP 200 with body `not JSON`, then `{}`, through HTTPX transport. | Convert invalid upstream content to `QAApiError`, allowing the handler to send a friendly failure message. | Unhandled `JSONDecodeError` or Pydantic `ValidationError` escapes `ask`; the handler catches only `QAApiError`. [Regression output](evidence/isolated_regressions.log). This is an injected dependency-response failure, not a claim that the current API normally emits these bodies. | `bot/api_client.py:24`: response decoding/validation outside the error translation in `_send`; `bot/main.py:65` catches only the wrapper. | Translate decoding/schema failures to the existing API error type and retain useful diagnostics in logs. |
| QA-08 | Medium | Bot input limit / misleading errors | VERIFIED | `-k long_valid_telegram`: pass 1,001 `x` characters through the actual question handler using real QA API HTTP. | Explain that the question exceeds the API's 1,000-character limit and ask for a shorter one. | API correctly returns 422, but bot says **`Xizmat vaqtincha ishlamayapti...`**, misleading the user into retrying an input that will always fail. [Regression output](evidence/isolated_regressions.log). | `app/api/schemas.py:5` limit not reflected in bot; `bot/api_client.py:32` collapses all status errors; `bot/main.py:65–67` labels all errors an outage. | Validate length at bot entry or preserve a typed validation error and show an actionable input message. |
| QA-09 | Critical | Startup dependency readiness | VERIFIED | `python3 qa/check_slow_start.py` uses `qa/slow-qdrant.yml` to delay only Qdrant's entrypoint by 30 seconds, then runs otherwise normal QA Compose `up -d api`; script restores the normal configuration afterward. | Ingest waits/retries until the started dependency is actually ready; API eventually starts. | Compose exits **1**: `service "ingest" didn't complete successfully: exit 1`; ingest raises `StorageUnavailableError: Qdrant bilan aloqa yo'q.` from connection refused. API never starts in that attempt. Normal configuration recovery exits 0. [Full reproduction](evidence/slow_start.log), [failing assertion](evidence/slow_start_result.log). | `docker-compose.yml:37`: Qdrant dependency uses `service_started`; `app/services/ingestion.py:41` immediately queries it; no readiness retry. | Add Qdrant readiness gating and bounded retries/backoff for transient startup connectivity failures. |
| QA-10 | Medium | Evaluation independence | VERIFIED | `PYTHONPATH=. .venv/bin/python qa/audit_eval.py`; `-k disjoint_holdout` checks the necessary condition that at least one nonempty evaluation set is query-disjoint from the calibration set. | Select threshold/rules on development data and publish final metrics on a frozen independent holdout. | `eval/evaluate.py` chooses the best threshold and reports it on the **same 245 queries**. EVALUATION.md explicitly says rules were adjusted using these errors. Only single-query and overlapping conversation sets exist. Coverage: **91/505 unique answers (~18%)**. [Audit](evidence/eval_audit.json). The figures are reproducible but not independent estimates. | `eval/evaluate.py:200–207`; `EVALUATION.md:17`. | Freeze a separate held-out set, track provenance, tune on development data only, and report production decision metrics alongside ranking/threshold metrics. The added disjointness test is necessary, not proof that nobody manually tuned against a holdout. |

## 3. Requirement coverage

| Requirement / check | Result | Evidence and qualification |
|---|---|---|
| Clean clone and no-cache image build | PASS | [clone](evidence/clone.log), [down -v](evidence/clean_down.log), [build](evidence/clean_build.log). Isolated named volumes and no reused model cache; application layers rebuilt. Existing global Docker base-image caches were not pruned. |
| README startup on available ports | PASS / PARTIAL | [isolated startup](evidence/isolated_start.log), 3,048 indexed questions. Image tags and host ports changed only for isolation. Real Telegram login not exercised. |
| Occupied ports | PASS | [original-port attempt](evidence/readme_up.log) exits 1 with `Bind for 127.0.0.1:5440 failed: port is already allocated`. Not counted as an application defect. |
| Slow dependency readiness | FAIL | QA-09. PostgreSQL is health-gated; Qdrant is merely start-gated. |
| Missing `.env` and empty/missing token | PASS | [env checks](evidence/env_checks.log): clear missing-file error and named Pydantic token validation errors. No token was invented or copied from the running bot. |
| Empty database URL | PARTIAL | Settings accepts `DATABASE_URL=''`; configuration-only probe verified acceptance, but full empty-URL startup behavior was not exercised. No unsupported bug claim is made. |
| Cold model download / first request | PASS | Fresh model volume and full ingestion succeeded; first post-readiness request 0.252 s. Compose return time excludes API warm-up. |
| Lint, type checking, existing tests | PASS | Working tree, clone with existing environment, and a newly installed environment all pass ruff/mypy and 83 pytest tests. See final validation addendum. |
| Empty, whitespace, 10k+ question, wrong JSON types/content type, malformed JSON | PASS | [input probes](evidence/read_api.jsonl), [additional probes](evidence/more_inputs.json): rejection with 422; friendly domain message for whitespace. |
| Emoji, mixed Latin/Cyrillic, special symbols, HTML/JS | PASS in sampled requests | 200 not-found for irrelevant symbols/snippets; mixed-script document question correctly answered. These are HTTP/JSON tests, not a browser XSS audit. |
| NUL in question/session/path | FAIL | QA-02; all three API entry paths reproduced. |
| Wrong extension, renamed text workbook, empty file, >10 MiB upload | PASS | [upload probes](evidence/uploads.jsonl): 422. |
| Corrupted XLSX internal XML | FAIL | QA-03. Both workbook XML and lazy worksheet XML tested. |
| Unicode workbook name, valid schema, missing columns, skipped/empty rows | PASS | [isolated imports](evidence/isolated_exercise.jsonl), [other workbooks](evidence/more_inputs.json). Unicode filename accepted. Header-only/fully skipped rows explicitly report zero imported records with 200. |
| Import idempotency | PASS for sequential retry | First synthetic import `newly_indexed=1`; second `0`; existing 3,048-row dataset reingest `0`. Simultaneous first-ever collection creation was not stress-tested. |
| SQL/vector consistency when import fails | FAIL | QA-04. Failed operation makes changed answer visible. |
| DB/vector-store outage and automatic recovery | PASS for search/health | Both produce Uzbek 503 details, then recover to 200. [lifecycle evidence](evidence/isolated_exercise.jsonl). |
| Bot API outage handling | PARTIAL | Ordinary question sends friendly outage message; `/new` falsely reports success (QA-06). Captured handler output with a real stopped API, without Telegram delivery. |
| Container restart and down/up persistence | PASS | Both return correct follow-up answer with `context_used=true`; volume-backed corpus remains queryable. |
| 20 parallel, 50 repeated requests / responsiveness / temp files | PASS for this bounded sample | 70/70 return 200; memory +~21 MiB; temp count unchanged; health responds during load. No long-duration leak claim. |
| Uzbek Latin/Cyrillic, no-match, ambiguity, conversational context | PARTIAL | Mixed-script and common follow-ups pass; published conversation set 12/15. Explicit wrong answers QA-01. Real HTTP corpus replay saved separately. |
| Return stored answer unchanged | FAIL in bot; PASS in sampled API replies | QA-05. HTTP evaluation compares answers with source text; bot truncates long source content. |
| Session separation / expiry / reset | PARTIAL | Existing real Postgres integration tests check independent session records and expiry; API DELETE Unicode/nonexistent sessions returns 204. No live multi-user Telegram group test; reset outage fails QA-06. |
| Local semantic model, no LLM generation | PASS for inspected search path | Model pinned to BAAI/bge-m3 revision; real embedding/ranking exercised. First model acquisition/build needs internet. No air-gapped installation test. |
| Reproduce reported metrics | PASS | [evaluation output](evidence/evaluation_run.log), [raw results](evidence/eval-results/metrics.json). |
| Separate tuning/evaluation and representative scope | FAIL / PARTIAL | QA-10; 245 developer-written queries, 59 OOD, 91/505 answer coverage and only 6 conversations/15 turns. There is no claim of statistical production representativeness. |
| Browser UI | PARTIAL | `/docs` and `/openapi.json` return 200. No product web UI exists; Swagger rendering/CDN availability was not browser-tested. |

### Reproduced metrics

| Metric | EVALUATION.md | Fresh model/index run |
|---|---:|---:|
| Recall@1 | 0.785 | 0.7849 |
| Recall@3 | 0.909 | 0.9086 |
| MRR | 0.849 | 0.8492 |
| OOD rejection F1 at 0.64 | 0.891 | 0.8906 |
| Conversation turns correct | 12/15 | 12/15 |

`python -m eval.evaluate` was executed from the clean built API image, with the committed evaluation package copied into `/tmp/eval`, `PYTHONPATH=/tmp:/srv`, and output redirected to `/tmp/qa-eval-results`. This avoids modifying the project's existing evaluation outputs. It uses freshly ingested data and the real model, Qdrant and PostgreSQL. Synthetic import records were removed from the isolated stores before evaluation. [Runner](eval_after_exercise.py) records the exact command. Runtime: 45.89 seconds. [HTTP replay](evidence/http_eval.json) separately exercises the actual API decision path rather than only `SearchService.rank`.

## 4. Tests and scripts added

- [test_regressions.py](test_regressions.py): intended-to-fail contracts for incorrect answers, NUL handling (including DELETE), corrupted workbook/worksheet XML, failed import publication, full bot-answer delivery, reset failure, invalid upstream bodies, long input handling, and missing independent evaluation data. These are not marked xfail.
- [check_slow_start.py](check_slow_start.py) + [slow-qdrant.yml](slow-qdrant.yml): startup fault-injection regression; restores normal configuration before asserting success. Currently exits 1.
- [probe_readonly.py](probe_readonly.py), [probe_uploads.py](probe_uploads.py), [probe_more_inputs.py](probe_more_inputs.py): exact inputs and retained responses for edge cases.
- [exercise_isolated.py](exercise_isolated.py): live 20/50-request load, memory/temp samples, dependency outages, restart/down/up, import idempotency and partial-commit reproduction. **Destructive only to the named QA project.**
- [probe_bot_outage.py](probe_bot_outage.py): real HTTP refusal, captured handler messages, API restored afterward.
- [audit_eval.py](audit_eval.py), [evaluate_http.py](evaluate_http.py), [eval_after_exercise.py](eval_after_exercise.py): dataset audit, real HTTP replay and original evaluator replay.
- [run_setup.py](run_setup.py), [run_isolated.py](run_isolated.py), [run_baseline.py](run_baseline.py), [run_clean_checks.py](run_clean_checks.py), [check_env.py](check_env.py): reproducible setup/baseline/environment checks. Disposable clone/venv are ignored by `qa/.gitignore`.
- [PLAN.md](PLAN.md) was written before executing the clean setup and adversarial probes. XLSX corruption fixtures are under `fixtures/`.

Existing tests are not empty: they assert storage joins, idempotency, session isolation, expiry, service decisions and request errors. However, most semantic service tests use a 64-dimensional hash/bag-of-words fake rather than bge-m3; they cannot establish real-language ranking quality. Bot tests mostly test formatting and even assert silent truncation. Existing integration tests skip if services are absent, so `pytest` alone is not evidence that live adapters ran; both services were available in this audit's runs.

## 5. Not tested / limits

- No original assignment checklist was attached, so no claim of compliance with unspecified requirements.
- No real Telegram account-to-bot delivery, group routing, flood limits or live Telegram API failure injection. Outgoing messages were captured locally; no user/bot credentials were exposed or messages sent to other people.
- No OCR dependency or PDF ingestion exists in this project. PDF/wrong extensions were tested as rejection cases, not supported features.
- No browser screenshot/rendering/accessibility audit; Swagger HTML and schema were retrieved through real HTTP.
- No destructive testing of the user's existing database, vector collection or model volume. All service stops, persistence tests and valid imports targeted the dedicated QA project.
- No deliberate disk exhaustion, multi-gigabyte HTTP body, highly expanding ZIP bomb, kernel OOM or hours-long soak. Tested oversized upload was 10 MiB + 1 byte. Short memory observations are not proof against gradual leaks.
- No simultaneous first-ever vector collection creation or competing distinct imports. The 20-request concurrency run was `/ask`, sharing four sessions.
- Empty storage URL validation was observed, but the full matrix of invalid hosts/credentials/empty values was not exhaustively started.
- No independent verification of the legal accuracy of the underlying answer texts. Correctness here means relevance and correspondence to the supplied corpus/annotations.
- No fixes, commits, deployments or Phase 2 work. Approval is required before remediation.

## 6. Final validation addendum

- **Fresh Python installation completed successfully** using the README extras in a new venv. See [installation log](evidence/clean_install.log) and [dependency snapshot](evidence/fresh_dependencies.txt). The host pip installation downloaded CUDA packages even though runtime configuration uses CPU; this was allowed to finish, not replaced with an unreported workaround.
- Fresh environment: [ruff passes](evidence/fresh_ruff.log); [mypy passes for 44 files](evidence/fresh_mypy.log); [pytest: 83 passed, 1 deprecation warning, 8.31 s](evidence/fresh_pytest.log). PostgreSQL and Qdrant integration tests ran against the isolated services; none were skipped.
- Final adversarial suite: **14 failed in 2.53 seconds**, covering nine finding groups; [exact final output](evidence/final_regressions.log). QA-09 separately has a **failing startup assertion** after restoring the normal configuration. Total: 15 failing test cases/assertions across ten finding groups. Earlier intermediate logs contain 10/12/13 failures as cases were added; this final log is authoritative.
- Final `ruff check .`, including the added QA Python files: [passes](evidence/final_ruff.log). No application files or pre-existing tests were edited. The working-tree diff remains the user's original changes plus `qa/`.
- Reproduction instructions and the reusable isolated-port override are in [qa/README.md](README.md) and [compose-isolated.yml](compose-isolated.yml).
- Cleanup: only QA containers were stopped after evidence collection. Their isolated volumes/model cache and clone remain for reproduction. The disposable 5.7 GiB clean-install venv and generated clone lint/test caches were removed after recording dependency versions and test results, avoiding a large accidental Docker build context. Recreate the clean venv using the commands in `qa/README.md`. The user's existing running services remain untouched.

**Phase 1 ends here. Awaiting approval of finding IDs before any fixes.**

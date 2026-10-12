# Reproducing Phase 1

Run from the project root. Application code is not modified. `task1_adversarial_qa` is the only Compose project that the destructive lifecycle scripts control. Do not substitute the name of the real deployment.

To recreate the disposable clone when absent:

```bash
git clone --no-hardlinks . qa/clean-clone
cp qa/clean-clone/.env.example qa/clean-clone/.env
cp qa/compose-isolated.yml qa/clean-clone/qa-isolated.yml
```

The clone is committed HEAD, not uncommitted working-tree changes. Keep the token empty for these local checks; scripts do not need Telegram login.

Build and start:

```bash
python3 qa/run_setup.py
python3 qa/run_isolated.py
```

`run_setup.py` deliberately attempts the original ports and records any collision before the isolated startup. It runs `down -v` only for the QA project. `run_isolated.py` runs the API and its dependencies, without the bot. Wait until `curl http://127.0.0.1:18000/health` returns 200; a fresh model download/index takes several minutes.

Assuming the project dependencies are installed into `.venv` as in the README:

```bash
QA_API_URL=http://127.0.0.1:18000 .venv/bin/python -m pytest qa/test_regressions.py -q
.venv/bin/python qa/exercise_isolated.py
PYTHONPATH=. .venv/bin/python qa/eval_after_exercise.py
PYTHONPATH=. .venv/bin/python qa/evaluate_http.py
python3 qa/check_slow_start.py
```

Run lifecycle scripts sequentially. `eval_after_exercise.py` waits for the exercise log's import-retry marker and removes only its synthetic QA records before running the original evaluator. Do not run it on an unrelated log or parallel to another lifecycle test. `check_slow_start.py` restores normal Compose configuration, then intentionally fails its readiness assertion on the current implementation.

`probe_readonly.py` and `probe_uploads.py` reproduce the initial probes against port **8000**; the regression suite uses `QA_API_URL` to repeat the findings against an isolated server. Valid ingestion and service-stop scripts always use port 18000/the QA project.

To repeat the clean Python installation and checks:

```bash
python3 -m venv qa/clean-venv
qa/clean-venv/bin/pip install -e 'qa/clean-clone[api,bot,dev]'
python3 qa/run_clean_checks.py
```

Evidence files are overwritten on rerun. Preserve them elsewhere first if comparing runs. Phase 1 regression failures are intentional; do not weaken assertions merely to obtain a green test result.

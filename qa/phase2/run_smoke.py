import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import psycopg
from qdrant_client import QdrantClient
from qdrant_client.models import PointIdsList

from app.domain.text import stable_id

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "qa/phase2"
CLONE = OUT / "clone"
BASE = "http://127.0.0.1:18000"
PYTHON = ROOT / ".venv/bin/python"
ENV = {
    **os.environ,
    "QA_API_URL": BASE,
    "QA_COMPOSE_DIR": str(CLONE),
    "QA_EVIDENCE_DIR": str(OUT),
    "TEST_DATABASE_URL": "postgresql://qa:qa@localhost:15440/qa",
    "TEST_QDRANT_URL": "http://localhost:16333",
}
COMPOSE = [
    "docker",
    "compose",
    "-p",
    "task1_adversarial_qa",
    "-f",
    str(CLONE / "docker-compose.yml"),
    "-f",
    str(CLONE / "qa-isolated.yml"),
]


def wait_ready(timeout=1200):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(BASE + "/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(3)
    raise RuntimeError("QA API failed to become ready")


def run(label, args, cwd=ROOT, timeout=1200):
    start = time.monotonic()
    with (OUT / f"{label}.log").open("w") as f:
        f.write("$ " + " ".join(map(str, args)) + "\n")
        f.flush()
        p = subprocess.run(args, cwd=cwd, env=ENV, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
        f.write(f"\nEXIT={p.returncode} ELAPSED={time.monotonic()-start:.2f}s\n")
    print(label, p.returncode, flush=True)
    return p.returncode


wait_ready()
run("regressions", [str(PYTHON), "-m", "pytest", "qa/test_regressions.py", "-q"])
for name in ["probe_readonly", "probe_uploads", "probe_more_inputs", "exercise_isolated"]:
    run(name, [str(PYTHON), f"qa/{name}.py"])
# Remove only the synthetic import used by the lifecycle exercise before evaluation.
qid = stable_id("QA audit unique passport procedure")
q = QdrantClient(url="http://127.0.0.1:16333")
q.delete(collection_name="qa_questions", points_selector=PointIdsList(points=[str(qid)]), wait=True)
q.close()
with psycopg.connect(ENV["TEST_DATABASE_URL"]) as c:
    c.execute("DELETE FROM questions WHERE id=%s", (qid,))
    c.execute(
        "DELETE FROM answers WHERE id=ANY(%s)",
        ([stable_id("QA original answer"), stable_id("QA changed despite failure")],),
    )
run("copy_eval", ["docker", "cp", str(CLONE / "eval"), "task1_adversarial_qa-api-1:/tmp/eval"])
run(
    "evaluation_dev",
    [
        "docker",
        "exec",
        "-e",
        "PYTHONPATH=/tmp:/srv",
        "task1_adversarial_qa-api-1",
        "python",
        "-m",
        "eval.evaluate",
        "--out",
        "/tmp/qa-dev-results",
    ],
)
run("prepare_replay", ["docker", "exec", "task1_adversarial_qa-api-1", "mkdir", "-p", "/tmp/qa-holdout-replay"])
run(
    "copy_frozen_plan",
    [
        "docker",
        "cp",
        str(OUT / "calibration/frozen_candidate.json"),
        "task1_adversarial_qa-api-1:/tmp/qa-holdout-replay/frozen_candidate.json",
    ],
)
run(
    "holdout_replay",
    [
        "docker",
        "exec",
        "-e",
        "PYTHONPATH=/tmp:/srv",
        "task1_adversarial_qa-api-1",
        "python",
        "-m",
        "eval.calibration",
        "holdout",
        "--out",
        "/tmp/qa-holdout-replay",
    ],
)
run("collect_dev", ["docker", "cp", "task1_adversarial_qa-api-1:/tmp/qa-dev-results", str(OUT / "dev-replay")])
run(
    "collect_holdout",
    ["docker", "cp", "task1_adversarial_qa-api-1:/tmp/qa-holdout-replay", str(OUT / "holdout-replay")],
)
run("slow_start_result", [str(PYTHON), "qa/check_slow_start.py"])
wait_ready(180)
# Fresh dependency environment may still be installing in parallel.
deadline = time.monotonic() + 1200
while not (OUT / "venv/bin/mypy").exists() or "Successfully installed" not in (OUT / "clean_install.log").read_text():
    if time.monotonic() > deadline:
        raise RuntimeError("clean dependency install timeout")
    time.sleep(3)
for name, args in [
    ("fresh_ruff", ["ruff", "check", "."]),
    ("fresh_mypy", ["mypy", "app", "bot", "tests", "eval"]),
    ("fresh_pytest", ["python", "-m", "pytest", "-q"]),
]:
    args[0] = str(OUT / "venv/bin" / args[0])
    run(name, args, cwd=CLONE)
run("fresh_dependencies", [str(OUT / "venv/bin/pip"), "freeze"])
(OUT / "smoke_complete.json").write_text(
    json.dumps(
        {
            "completed": True,
            "context_decision": "pending; QA-02 unchanged",
            "known_residual": "QA-01 high-score wrong acceptances remain",
        },
        indent=2,
    )
)

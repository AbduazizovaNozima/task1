import concurrent.futures
import io
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get("QA_EVIDENCE_DIR", ROOT / "evidence"))
CLONE = Path(os.environ.get("QA_COMPOSE_DIR", ROOT / "clean-clone"))
BASE = "http://127.0.0.1:18000"
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
f = (OUT / "isolated_exercise.jsonl").open("w")


def log(label, **data):
    row = {"label": label, **data}
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
    f.flush()
    print(str(row)[:600], flush=True)


def command(*args):
    p = subprocess.run(COMPOSE + list(args), capture_output=True, text=True)
    log("compose", args=args, status=p.returncode, output=p.stdout + p.stderr)
    return p


def req(method, path, **kwargs):
    t = time.monotonic()
    try:
        r = httpx.request(method, BASE + path, timeout=90, **kwargs)
        return {"status": r.status_code, "body": r.text, "seconds": round(time.monotonic() - t, 3)}
    except Exception as e:
        return {"error": repr(e), "seconds": round(time.monotonic() - t, 3)}


def healthwait(timeout=1200):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if httpx.get(BASE + "/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(3)
    raise RuntimeError("API failed to become ready")


healthwait()
log("first_ask", **req("POST", "/ask", json={"question": "ID karta olish uchun nima kerak?"}))


def stats(label):
    p = subprocess.run(
        [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{.Name}} {{.MemUsage}} {{.PIDs}}",
            "task1_adversarial_qa-api-1",
        ],
        capture_output=True,
        text=True,
    )
    q = command("exec", "-T", "api", "sh", "-c", "find /tmp -type f | wc -l")
    log(label, memory=p.stdout, temp_files=q.stdout)


stats("before_load")


def ask(i):
    return req("POST", "/ask", json={"question": "ID karta olish uchun nima kerak?", "session_id": f"qa-load-{i%4}"})


t = time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
    futures = [pool.submit(ask, i) for i in range(20)]
    log("health_during_load", **req("GET", "/health"))
    responses = [x.result() for x in futures]
log("parallel_20", seconds=time.monotonic() - t, responses=responses)
log("sequential_50", responses=[ask(i) for i in range(50)])
stats("after_load")
for service in ["qdrant", "postgres"]:
    try:
        command("stop", service)
        log(service + "_down_health", **req("GET", "/health"))
        log(
            service + "_down_ask",
            **req("POST", "/ask", json={"question": "ID karta olish uchun nima kerak?", "session_id": "qa-outage"}),
        )
    finally:
        command("start", service)
    healthwait(120)
    log(service + "_recovered", **req("POST", "/ask", json={"question": "ID karta olish uchun nima kerak?"}))

# Test stale state is still there after restart and down/up without -v.
req("POST", "/ask", json={"question": "ID karta olish uchun nima kerak?", "session_id": "qa-persistence"})
for label, args in [("restart", ["restart", "api"]), ("down", ["down"]), ("up", ["up", "-d", "api"])]:
    command(*args)
    if label != "down":
        healthwait(180)
        log(
            label + "_persistence",
            **req("POST", "/ask", json={"question": "muddati-chi?", "session_id": "qa-persistence"}),
        )
        req("POST", "/ask", json={"question": "ID karta olish uchun nima kerak?", "session_id": "qa-persistence"})


# Real data import, Unicode name, idempotency and partial commit on vector outage.
def sheet(answer):
    b = io.BytesIO()
    w = Workbook()
    w.active.append(["question", "answer"])
    w.active.append(["QA audit unique passport procedure", answer])
    w.save(b)
    return b.getvalue()


for i in range(2):
    log(
        "ingest_idempotent_" + str(i),
        **req("POST", "/ingest", files={"file": ("ўзбек.xlsx", sheet("QA original answer"))}),
    )
try:
    command("stop", "qdrant")
    log(
        "ingest_during_vector_outage",
        **req("POST", "/ingest", files={"file": ("qa.xlsx", sheet("QA changed despite failure"))}),
    )
finally:
    command("start", "qdrant")
healthwait(120)
log("answer_after_failed_ingest", **req("POST", "/ask", json={"question": "QA audit unique passport procedure"}))
log("retry_ingest", **req("POST", "/ingest", files={"file": ("qa.xlsx", sheet("QA original answer"))}))
command("logs", "--no-color", "--tail=150", "api", "ingest")
f.close()

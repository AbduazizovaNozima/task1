import subprocess
import time
from pathlib import Path

import psycopg
from qdrant_client import QdrantClient
from qdrant_client.models import PointIdsList

from app.domain.text import stable_id

ROOT = Path(__file__).resolve().parent
while True:
    p = ROOT / "evidence/isolated_exercise.jsonl"
    if p.exists() and "retry_ingest" in p.read_text():
        break
    time.sleep(3)
# Remove only synthetic QA records before rerunning published metrics.
qid = stable_id("QA audit unique passport procedure")
q = QdrantClient(url="http://127.0.0.1:16333")
q.delete(collection_name="qa_questions", points_selector=PointIdsList(points=[str(qid)]), wait=True)
q.close()
with psycopg.connect("postgresql://qa:qa@127.0.0.1:15440/qa") as c:
    c.execute("DELETE FROM questions WHERE id=%s", (qid,))
    c.execute(
        "DELETE FROM answers WHERE id=ANY(%s)",
        ([stable_id("QA original answer"), stable_id("QA changed despite failure")],),
    )
subprocess.run(["docker", "cp", str(ROOT / "clean-clone/eval"), "task1_adversarial_qa-api-1:/tmp/eval"], check=True)
start = time.monotonic()
with (ROOT / "evidence/evaluation_run.log").open("w") as f:
    p = subprocess.run(
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
            "/tmp/qa-eval-results",
        ],
        stdout=f,
        stderr=subprocess.STDOUT,
    )
    f.write(f"\nEXIT={p.returncode} ELAPSED={time.monotonic()-start:.2f}s\n")
subprocess.run(
    ["docker", "cp", "task1_adversarial_qa-api-1:/tmp/qa-eval-results", str(ROOT / "evidence/eval-results")], check=True
)
print("evaluation complete", p.returncode, flush=True)

import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
clone = Path(os.environ.get("QA_COMPOSE_DIR", root / "clean-clone"))
out = Path(os.environ.get("QA_EVIDENCE_DIR", root / "evidence"))
base = [
    "docker",
    "compose",
    "-p",
    "task1_adversarial_qa",
    "-f",
    str(clone / "docker-compose.yml"),
    "-f",
    str(clone / "qa-isolated.yml"),
]
slow = [*base, "-f", str(root / "slow-qdrant.yml")]
results = []
with (out / "slow_start.log").open("w") as f:
    for args in [
        [*base, "down"],
        [*slow, "up", "-d", "api"],
        [*slow, "logs", "--no-color", "--tail=60", "ingest", "qdrant"],
    ]:
        f.write("$ " + " ".join(args) + "\n")
        f.flush()
        p = subprocess.run(args, stdout=f, stderr=subprocess.STDOUT, timeout=180)
        f.write(f"EXIT={p.returncode}\n")
        f.flush()
        results.append(p.returncode)
    # Always restore the regular QA configuration.
    p = subprocess.run([*base, "up", "-d", "api"], stdout=f, stderr=subprocess.STDOUT, timeout=180)
    f.write(f"RECOVERY_EXIT={p.returncode}\n")

assert results[1] == 0, "API startup failed when Qdrant needed 30 seconds to become ready; see evidence/slow_start.log"

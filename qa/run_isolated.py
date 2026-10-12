import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent
cmd = ["docker", "compose", "-p", "task1_adversarial_qa", "-f", "docker-compose.yml", "-f", "qa-isolated.yml"]
with (root / "evidence/isolated_start.log").open("w") as f:
    t = time.monotonic()
    p = subprocess.run([*cmd, "up", "-d", "api"], cwd=root / "clean-clone", stdout=f, stderr=subprocess.STDOUT)
    f.write(f"\nEXIT={p.returncode} ELAPSED={time.monotonic()-t:.2f}s\n")
print("isolated startup", p.returncode, flush=True)

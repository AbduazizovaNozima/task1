import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLONE = ROOT / "clean-clone"


def run(name, command, timeout=1800):
    start = time.monotonic()
    with (ROOT / "evidence" / f"{name}.log").open("w") as f:
        f.write("$ " + command + "\n")
        f.flush()
        try:
            p = subprocess.run(
                command,
                shell=True,
                cwd=CLONE,
                stdout=f,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                env={**os.environ, "COMPOSE_PROJECT_NAME": "task1_adversarial_qa"},
            )
            code = p.returncode
        except subprocess.TimeoutExpired:
            code = "TIMEOUT"
        f.write(f"\nEXIT={code} ELAPSED={time.monotonic()-start:.2f}s\n")
    print(name, code, flush=True)


# Separate image tags so QA does not overwrite the image of the running application.
(CLONE / "qa-build.yml").write_text(
    "services:\n  ingest:\n    image: task1-adversarial-qa\n  api:\n    image: task1-adversarial-qa\n"
)
run("clean_down", "docker compose down -v")
run("clean_build", "docker compose -f docker-compose.yml -f qa-build.yml build --no-cache", 1800)
run("readme_up", "docker compose -f docker-compose.yml -f qa-build.yml up -d --build", 300)

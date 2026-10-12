import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
for name, args in [
    ("fresh_ruff", ["ruff", "check", "."]),
    ("fresh_mypy", ["mypy", "app", "bot", "tests", "eval"]),
    ("fresh_pytest", ["python", "-m", "pytest", "-q"]),
]:
    args[0] = str(root / "clean-venv/bin" / args[0])
    with (root / "evidence" / f"{name}.log").open("w") as f:
        p = subprocess.run(
            args,
            cwd=root / "clean-clone",
            env={
                **os.environ,
                "TEST_DATABASE_URL": "postgresql://qa:qa@localhost:15440/qa",
                "TEST_QDRANT_URL": "http://localhost:16333",
            },
            stdout=f,
            stderr=subprocess.STDOUT,
        )
        f.write(f"\nEXIT={p.returncode}\n")
    print(name, p.returncode, flush=True)

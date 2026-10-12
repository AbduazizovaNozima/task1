import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
python = root / ".venv/bin/python"
for name, args, cwd in [
    ("working_ruff", [str(root / ".venv/bin/ruff"), "check", "app", "bot", "tests", "eval"], root),
    ("working_mypy", [str(root / ".venv/bin/mypy"), "app", "bot", "tests", "eval"], root),
    ("working_pytest", [str(python), "-m", "pytest", "-q"], root),
    ("clone_ruff", [str(root / ".venv/bin/ruff"), "check", "."], root / "qa/clean-clone"),
    ("clone_mypy", [str(root / ".venv/bin/mypy"), "app", "bot", "tests", "eval"], root / "qa/clean-clone"),
    ("clone_pytest", [str(python), "-m", "pytest", "-q"], root / "qa/clean-clone"),
]:
    with (root / f"qa/evidence/{name}.log").open("w") as f:
        start = time.monotonic()
        p = subprocess.run(args, cwd=cwd, stdout=f, stderr=subprocess.STDOUT)
        f.write(f"\nEXIT={p.returncode} ELAPSED={time.monotonic()-start:.2f}s\n")
    print(name, p.returncode, flush=True)

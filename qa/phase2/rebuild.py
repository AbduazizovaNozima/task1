import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "qa/phase2"
CLONE = OUT / "clone"
assert not CLONE.exists(), "Use a fresh snapshot directory; do not overwrite evidence"
subprocess.run(["git", "clone", "--no-hardlinks", str(ROOT), str(CLONE)], check=True)
# Export the approved working tree, including uncommitted fixes, into the new clone.
for name in ["app", "bot", "data", "eval", "tests"]:
    target = CLONE / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ROOT / name, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "results"))
for name in [
    ".dockerignore",
    ".gitignore",
    ".env.example",
    "Dockerfile",
    "pyproject.toml",
    "docker-compose.yml",
    "README.md",
    "EVALUATION.md",
]:
    shutil.copy2(ROOT / name, CLONE / name)
shutil.copy2(CLONE / ".env.example", CLONE / ".env")
override = (ROOT / "qa/compose-isolated.yml").read_text().replace("task1-adversarial-qa", "task1-adversarial-qa-phase2")
(CLONE / "qa-isolated.yml").write_text(override)
manifest = {
    str(p.relative_to(CLONE)): hashlib.sha256(p.read_bytes()).hexdigest()
    for name in ["app", "bot", "eval", "tests"]
    for p in (CLONE / name).rglob("*")
    if p.is_file()
}
(OUT / "source_manifest.json").write_text(json.dumps(manifest, indent=2))
compose = [
    "docker",
    "compose",
    "-p",
    "task1_adversarial_qa",
    "-f",
    str(CLONE / "docker-compose.yml"),
    "-f",
    str(CLONE / "qa-isolated.yml"),
]
for label, args in [
    ("clean_down", ["down", "-v"]),
    ("clean_build", ["build", "--no-cache"]),
    ("clean_up", ["up", "-d", "api"]),
]:
    start = time.monotonic()
    with (OUT / f"{label}.log").open("w") as f:
        f.write("$ " + " ".join([*compose, *args]) + "\n")
        f.flush()
        result = subprocess.run([*compose, *args], stdout=f, stderr=subprocess.STDOUT, timeout=1800)
        f.write(f"\nEXIT={result.returncode} ELAPSED={time.monotonic()-start:.2f}s\n")
    print(label, result.returncode, flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)

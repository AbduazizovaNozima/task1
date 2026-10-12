import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
python = root / ".venv/bin/python"
with (root / "qa/evidence/env_checks.log").open("w") as f, tempfile.TemporaryDirectory() as d:
    base = {k: v for k, v in os.environ.items() if k not in ("TELEGRAM_BOT_TOKEN", "DATABASE_URL", "QDRANT_URL")}
    base["PYTHONPATH"] = str(root)
    for label, code, extra in [
        ("missing token", "from bot.config import BotSettings; BotSettings()", {}),
        ("empty token", "from bot.config import BotSettings; BotSettings()", {"TELEGRAM_BOT_TOKEN": ""}),
        (
            "empty database URL",
            "from app.config import Settings; print(repr(Settings().database_url))",
            {"DATABASE_URL": ""},
        ),
        ("missing env compose", "", {}),
    ]:
        if not code:
            continue
        p = subprocess.run([str(python), "-c", code], cwd=d, env={**base, **extra}, capture_output=True, text=True)
        f.write(f"{label}: exit={p.returncode}\n{p.stdout}{p.stderr}\n")
    # Config-only check with a nonexistent env file, no live services touched.
    text = (root / "docker-compose.yml").read_text().replace("env_file: .env", "env_file: nonexistent.env")
    path = Path(d) / "compose.yml"
    path.write_text(text)
    p = subprocess.run(["docker", "compose", "-f", str(path), "config", "--quiet"], capture_output=True, text=True)
    f.write(f"missing .env: exit={p.returncode}\n{p.stdout}{p.stderr}")

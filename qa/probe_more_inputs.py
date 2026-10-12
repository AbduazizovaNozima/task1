import io
import json
import os
from pathlib import Path

import httpx
from openpyxl import Workbook

BASE = "http://127.0.0.1:18000"
rows = []


def request(method, path, **kwargs):
    r = httpx.request(method, BASE + path, timeout=90, **kwargs)
    row = {"method": method, "path": path, "status": r.status_code, "body": r.text[:700]}
    rows.append(row)
    print(row, flush=True)


for path in ["/docs", "/openapi.json", "/health"]:
    request("GET", path)
for payload in [
    {"question": None},
    {"question": []},
    {"question": "x", "session_id": ""},
    {"question": "x", "session_id": "s" * 101},
    {"question": "\u200b"},
    {"question": "Id карта олиш uchun nima kerak?"},
]:
    request("POST", "/ask", json=payload)
    rows[-1]["input"] = payload
for session in ["ўзбек-qa", "new-nonexistent", "qa%00null"]:
    request("DELETE", "/sessions/" + session)
for data in [[], [["wrong", "header"]], [["question", "answer"]], [["question", "answer"], ["", "value"], ["q", ""]]]:
    b = io.BytesIO()
    w = Workbook()
    for row in data:
        w.active.append(row)
    w.save(b)
    request("POST", "/ingest", files={"file": ("empty-content.xlsx", b.getvalue())})
    rows[-1]["rows"] = data
request("POST", "/ingest", json={"file": "not multipart"})
(Path(os.environ.get("QA_EVIDENCE_DIR", Path(__file__).parent / "evidence")) / "more_inputs.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=2)
)

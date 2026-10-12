import io
import json
import os
import zipfile
from pathlib import Path

import httpx
from openpyxl import Workbook

root = Path(__file__).parent
b = io.BytesIO()
w = Workbook()
w.active.append(["question", "answer"])
w.save(b)


def corrupt(member, content):
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(b.getvalue())) as src, zipfile.ZipFile(out, "w") as dst:
        for n in src.namelist():
            dst.writestr(n, content if n == member else src.read(n))
    return out.getvalue()


fixtures = {
    "malformed-xml.xlsx": corrupt("xl/workbook.xml", b"<broken"),
    "malformed-sheet.xlsx": corrupt("xl/worksheets/sheet1.xml", b"<broken"),
    "empty.xlsx": b"",
    "renamed.xlsx": b"not excel",
    "wrong.pdf": b"not pdf",
    "large.xlsx": b"x" * (10 * 1024 * 1024 + 1),
    "unicode-ўзбек.xlsx": b"not excel",
}
(root / "fixtures").mkdir(exist_ok=True)
with (Path(os.environ.get("QA_EVIDENCE_DIR", root / "evidence")) / "uploads.jsonl").open("w") as f:
    for name, data in fixtures.items():
        if len(data) < 100000:
            (root / "fixtures" / name).write_bytes(data)
        with httpx.Client(timeout=60) as c:
            r = c.post(os.environ.get("QA_API_URL", "http://127.0.0.1:8000") + "/ingest", files={"file": (name, data)})
            row = {"file": name, "size": len(data), "status": r.status_code, "body": r.text[:1000]}
            print(row, flush=True)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()

import json
import os
import time
from pathlib import Path

import httpx

out = Path(os.environ.get("QA_EVIDENCE_DIR", Path(__file__).parent / "evidence")) / "read_api.jsonl"
cases = [
    ("", None),
    ("   ", None),
    ("x" * 10001, None),
    ("😀🫠🎈", None),
    ("ID карта olish учун nima kerak?", None),
    ("' \" < > & % _ \\ ; --", None),
    ("<script>alert(1)</script>", None),
    ("ID karta olish uchun nima kerak?", "qa-null\x00session"),
    ("ID karta\x00olish uchun nima kerak?", None),
    ("pensiya nechpul", None),
    ("ID-karta narxi", None),
    ("pasport", None),
    ("ID karta olish uchun nima kerak?", None),
    ("amir temur qachon nikoh qurgan?", None),
]
with httpx.Client(base_url=os.environ.get("QA_API_URL", "http://127.0.0.1:8000"), timeout=120) as c, out.open("w") as f:

    def save(data):
        f.write(json.dumps(data, ensure_ascii=False) + "\n")
        f.flush()
        print(str(data)[:700], flush=True)

    for q, s in cases:
        p = {"question": q}
        if s is not None:
            p["session_id"] = s
        t = time.monotonic()
        try:
            r = c.post("/ask", json=p)
            save(
                {"input": p, "status": r.status_code, "body": r.text[:3000], "seconds": round(time.monotonic() - t, 3)}
            )
        except Exception as e:
            save({"input": p, "error": repr(e)})
    for data, ct in [
        (b"{}", "application/json"),
        (b"null", "application/json"),
        (b"{", "application/json"),
        (b'{"question":42}', "application/json"),
        (b'{"question":"pasport"}', "text/plain"),
    ]:
        r = c.post("/ask", content=data, headers={"Content-Type": ct})
        save({"raw": data.decode(), "content_type": ct, "status": r.status_code, "body": r.text[:1000]})

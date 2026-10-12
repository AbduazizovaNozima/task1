import datetime
import io
import json
import time
from pathlib import Path

import httpx
import psycopg
from openpyxl import Workbook
from qdrant_client import QdrantClient

from app.domain.query import expand
from app.domain.text import normalize

OUT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:18000"
DB = "postgresql://qa:qa@localhost:15440/qa"
rows = []


def request(label, method, path, **kwargs):
    start = time.monotonic()
    with httpx.Client(timeout=90) as c:
        r = c.request(method, BASE + path, **kwargs)
    try:
        body = r.json()
    except ValueError:
        body = r.text
    row = {
        "case": label,
        "method": method,
        "path": path,
        "status": r.status_code,
        "body": body,
        "seconds": time.monotonic() - start,
    }
    rows.append(row)
    print(str(row)[:650], flush=True)
    return row


def sheet(data, configure=None):
    w = Workbook()
    for row in data:
        w.active.append(row)
    if configure:
        configure(w)
    out = io.BytesIO()
    w.save(out)
    return out.getvalue()


def upload(label, data, configure=None, name="check.xlsx"):
    return request(label, "POST", "/ingest", files={"file": (name, sheet(data, configure))})


def counts():
    with psycopg.connect(DB) as c:
        sql = {key: c.execute(f"SELECT count(*) FROM {key}").fetchone()[0] for key in ["questions", "answers"]}
    with QdrantClient(url="http://localhost:16333") as client:
        sql["vectors"] = client.count("qa_questions", exact=True).count
    return sql


header = ["question", "answer"]
fixtures = [
    (
        "empty_and_partial",
        [
            header,
            [None, None],
            ["QA partial question", None],
            [None, "QA partial answer"],
            ["QA checklist valid question", "QA valid answer"],
        ],
    ),
    (
        "duplicates",
        [header, ["QA duplicate question", "QA first answer"], ["QA duplicate question", "QA final answer"]],
    ),
    ("whitespace", [header, ["  QA spaces question  ", "  QA spaces answer  "]]),
    ("line_breaks", [header, ["QA line\nbreak question", "QA line\nbreak answer"]]),
    ("formula", [header, ['="QA formula question"', "QA formula answer"]]),
    ("number_date", [header, [123456789, datetime.datetime(2024, 1, 2)]]),
    ("extra_column", [["question", "answer", "extra"], ["QA extra question", "QA extra answer", "ignored"]]),
    ("renamed_columns", [["savol", "javob"], ["QA renamed", "QA answer"]]),
    ("header_row_two", [["Intro"], header, ["QA below header", "QA answer"]]),
]
for label, data in fixtures:
    upload(label, data)
upload(
    "merged_cells",
    [header, ["QA merged question", "QA upper answer"], [None, "QA lower answer"]],
    lambda w: w.active.merge_cells("A2:A3"),
)


def multiple(w):
    other = w.create_sheet("Second")
    other.append(header)
    other.append(["QA second-sheet question", "QA second-sheet answer"])
    w.active = 1


upload("multiple_sheets_active_second", [header, ["QA first-sheet question", "QA first-sheet answer"]], multiple)
upload("xls_extension", [header, ["QA xls", "QA answer"]], name="renamed.xls")
repeat = [header, ["QA stable identity question", "QA stable identity answer"]]
upload("counts_first", repeat)
first = counts()
upload("counts_second", repeat)
second = counts()
rows.append({"case": "idempotency_counts", "first": first, "second": second, "identical": first == second})
initial = [header, ["QA updated question", "QA answer before"], ["QA removed question", "QA retained answer"]]
upload("update_initial", initial)
upload("update_changed_and_removed", [header, ["QA updated question", "QA answer after"]])
for label, q in [("changed_answer", "QA updated question"), ("removed_row", "QA removed question")]:
    request(label, "POST", "/ask", json={"question": q})
queries = {
    "exact": "ID-karta olish uchun qanday hujjatlar kerak?",
    "paraphrase": "ID olishga hujjatlardan nimalarni tayyorlab borsam bo‘ladi?",
    "typo": "ID karta olsh uchun qanaqa hujjat kere?",
    "cyrillic": "ИД карта олиш учун қандай ҳужжатлар керак?",
    "russian": "Какие документы нужны для получения ID-карты?",
    "all_caps": "ID-KARTA OLISH UCHUN QANDAY HUJJATLAR KERAK?",
    "single_word": "nikoh",
    "long": "q" * 10001,
    "unrelated": "Menga shokoladli tort retseptini yozib bering",
}
for mark in ["‘", "'", "ʻ", "`"]:
    queries["apostrophe_" + mark] = "O" + mark + "qishni boshqa OTMga ko" + mark + "chirish qanday amalga oshiriladi?"
for label, q in queries.items():
    row = request(label, "POST", "/ask", json={"question": q})
    row["question"] = q
    if row["status"] == 200:
        row["schema_consistent"] = set(row["body"]) == {
            "found",
            "answer",
            "matched_question",
            "score",
            "suggestions",
            "context_used",
        }
# Near-threshold examples come from development data only, never held-out errors.
legacy = json.loads((Path(__file__).resolve().parents[1] / "evidence/eval-results/failures.json").read_text())
near = sorted(
    {x["query"]: x for group in legacy.values() for x in group}.values(), key=lambda x: abs(x["score"] - 0.67)
)[:6]
for item in near:
    request("near_threshold_dev", "POST", "/ask", json={"question": item["query"]})
with psycopg.connect(DB) as c:
    records = {str(qid): str(aid) for qid, aid in c.execute("SELECT id,answer_id FROM questions")}
points = {}
with QdrantClient(url="http://localhost:16333") as c:
    offset = None
    while True:
        batch, offset = c.scroll("qa_questions", limit=256, offset=offset, with_payload=True, with_vectors=False)
        points.update((str(p.id), str(p.payload["answer_id"])) for p in batch)
        if offset is None:
            break
rows.append(
    {
        "case": "sql_vector_identity",
        "sql_questions": len(records),
        "vector_points": len(points),
        "same_ids": records.keys() == points.keys(),
        "same_answer_ids": records == points,
    }
)
rows.append(
    {
        "case": "normalization",
        "input": "  ЎҚИШ  prava  ",
        "ingest": normalize("  ЎҚИШ  prava  "),
        "query": expand("  ЎҚИШ  prava  "),
        "same": normalize("  ЎҚИШ  prava  ") == expand("  ЎҚИШ  prava  "),
    }
)
(OUT / "checklist_api.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))

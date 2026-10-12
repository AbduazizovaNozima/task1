import json
from pathlib import Path

import httpx

from app.adapters.excel_reader import read_qa_sheet
from app.domain.text import normalize

root = Path(__file__).resolve().parents[1]
reference = {normalize(p.question): p.answer for p in read_qa_sheet(root / "data/qa.xlsx").pairs}
items = [json.loads(s) for s in (root / "eval/dev.jsonl").read_text().splitlines() if s.strip()]
results = []
with httpx.Client(base_url="http://127.0.0.1:18000", timeout=90) as c:
    for row in items:
        r = c.post("/ask", json={"question": row["query"]})
        expected = {reference[normalize(q)] for q in row["expected"]}
        actual = r.json()
        correct = (actual.get("found") and actual.get("answer") in expected) if expected else not actual.get("found")
        results.append(
            {
                "query": row["query"],
                "expected_questions": row["expected"],
                "status": r.status_code,
                "correct": bool(correct),
                "actual": actual,
            }
        )
summary = {
    "total": len(results),
    "correct": sum(r["correct"] for r in results),
    "wrong_answer_found_true": sum(r["actual"].get("found", False) and not r["correct"] for r in results),
    "http_errors": sum(r["status"] != 200 for r in results),
    "in_domain_rejected": sum(bool(r["expected_questions"]) and not r["actual"].get("found") for r in results),
}
(root / "qa/evidence/http_eval.json").write_text(
    json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2)
)
print(summary)

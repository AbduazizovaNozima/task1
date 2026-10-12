import json
from pathlib import Path

from app.adapters.excel_reader import read_qa_sheet
from app.domain.text import normalize, stable_id

root = Path(__file__).resolve().parents[1]
items = [json.loads(s) for s in (root / "eval/dev.jsonl").read_text().splitlines() if s.strip()]
pairs = read_qa_sheet(root / "data/qa.xlsx").pairs
questions = {normalize(p.question) for p in pairs}
answers = {stable_id(p.answer) for p in pairs}
reference = {normalize(p.question): stable_id(p.answer) for p in pairs}
covered = {reference[normalize(q)] for row in items for q in row["expected"]}
report = {
    "total_queries": len(items),
    "in_domain": sum(bool(x["expected"]) for x in items),
    "ood": sum(not x["expected"] for x in items),
    "distinct_queries": len({normalize(x["query"]) for x in items}),
    "corpus_rows": len(pairs),
    "unique_answers": len(answers),
    "evaluated_answers": len(covered),
    "exact_query_overlap_with_corpus": [x["query"] for x in items if normalize(x["query"]) in questions],
    "evaluation_files": [str(p.relative_to(root)) for p in (root / "eval").glob("*.jsonl")],
    "tuning_admission": [s for s in (root / "EVALUATION.md").read_text().splitlines() if "Cheklov" in s],
}
(root / "qa/evidence/eval_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False, indent=2))

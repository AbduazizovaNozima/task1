"""Evaluate single-question decisions on development data at the configured threshold."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from app.adapters.excel_reader import read_qa_sheet
from app.config import Settings
from app.container import build_container
from app.domain.query import is_ambiguous
from app.domain.text import stable_id
from app.log import configure_logging
from app.services.ingestion import to_records
from app.services.search import SearchService

EVAL_DIR = Path(__file__).parent


class EvalItem(BaseModel):
    query: str
    expected: list[str]


@dataclass(frozen=True)
class Reference:
    answer_of: dict[UUID, UUID]


def load_reference(sheet_path: Path) -> Reference:
    _, questions = to_records(read_qa_sheet(sheet_path).pairs)
    return Reference(
        answer_of={q.id: q.answer_id for q in questions},
    )


@dataclass(frozen=True)
class Observation:
    expected: frozenset[str]
    first: str | None
    score: float
    ambiguous: bool
    rank: int | None


def collect(search: SearchService, path: Path, reference: Reference, settings: Settings) -> list[Observation]:
    observations = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = EvalItem.model_validate_json(line)
        hits = search.rank(item.query)
        expected = frozenset(str(reference.answer_of[stable_id(text)]) for text in item.expected)
        ranked = [str(hit.answer_id) for hit in hits]
        ambiguous = is_ambiguous(
            item.query,
            [hit.score for hit in hits[: settings.search_top_k]],
            settings.ambiguity_margin,
            settings.ambiguity_max_words,
        )
        observations.append(
            Observation(
                expected,
                ranked[0] if ranked else None,
                hits[0].score if hits else 0.0,
                ambiguous,
                next((i for i, value in enumerate(ranked, 1) if value in expected), None),
            )
        )
    return observations


def metrics(rows: list[Observation], threshold: float) -> dict[str, float]:
    in_domain = sum(bool(row.expected) for row in rows)
    ood = len(rows) - in_domain
    accepted = [row for row in rows if row.first is not None and row.score >= threshold and not row.ambiguous]
    good = sum(row.first in row.expected for row in accepted)
    wrong = len(accepted) - good
    false_accepts = sum(not row.expected for row in accepted)
    false_rejects = in_domain - sum(bool(row.expected) for row in accepted)
    rejected_ood = ood - false_accepts
    denom = 2 * rejected_ood + false_rejects + false_accepts
    return {
        "threshold": threshold,
        "queries": len(rows),
        "in_domain": in_domain,
        "ood": ood,
        "correct_accepted": good,
        "wrong_accepted": wrong,
        "false_acceptances": false_accepts,
        "false_rejections": false_rejects,
        "decision_accuracy": (good + rejected_ood) / len(rows),
        "in_domain_correct_rate": good / in_domain,
        "accepted_precision": good / len(accepted) if accepted else 0.0,
        "ood_rejection_f1": 2 * rejected_ood / denom if denom else 0.0,
        "recall_at_1": sum(row.rank == 1 for row in rows if row.expected) / in_domain,
        "recall_at_3": sum(row.rank is not None and row.rank <= 3 for row in rows if row.expected) / in_domain,
        "mrr": sum(1 / row.rank for row in rows if row.expected and row.rank) / in_domain,
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m eval.evaluate")
    parser.add_argument("--dataset", type=Path, default=EVAL_DIR / "dev.jsonl")
    parser.add_argument("--sheet", type=Path, default=Path("data/qa.xlsx"))
    parser.add_argument("--out", type=Path, default=EVAL_DIR / "results" / "dev")
    args = parser.parse_args()
    if args.dataset.resolve() != (EVAL_DIR / "dev.jsonl").resolve():
        parser.error("Only dev.jsonl is evaluated; frozen holdout results are preserved in EVALUATION.md")
    configure_logging("WARNING")
    settings = Settings()
    reference = load_reference(args.sheet)
    container = build_container(settings)
    try:
        observations = collect(container.search, args.dataset, reference, settings)
    finally:
        container.close()
    report = metrics(observations, settings.match_threshold)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

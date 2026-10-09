import argparse
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from app.adapters.excel_reader import read_qa_sheet
from app.config import Settings
from app.container import build_container
from app.domain.text import stable_id
from app.log import configure_logging
from app.services.conversation import ConversationService
from app.services.ingestion import to_records
from app.services.search import SearchService

EVAL_DIR = Path(__file__).parent
THRESHOLDS = [round(0.30 + 0.01 * step, 2) for step in range(61)]
TABLE_STEP = 5


class EvalItem(BaseModel):
    query: str
    expected: list[str]


class Scenario(BaseModel):
    name: str
    turns: list[EvalItem]


@dataclass(frozen=True)
class Reference:
    answer_of: dict[UUID, UUID]
    question_text: dict[UUID, str]


@dataclass(frozen=True)
class Outcome:
    query: str
    expected: frozenset[UUID]
    ranked: list[UUID]
    top_score: float
    top_question: str | None

    @property
    def in_domain(self) -> bool:
        return bool(self.expected)

    @property
    def rank(self) -> int | None:
        return next((i for i, answer in enumerate(self.ranked, start=1) if answer in self.expected), None)


@dataclass(frozen=True)
class ThresholdPoint:
    threshold: float
    precision: float
    recall: float
    f1: float
    answered_correctly: float
    false_rejections: int
    false_acceptances: int


def load_reference(sheet_path: Path) -> Reference:
    _, questions = to_records(read_qa_sheet(sheet_path).pairs)
    return Reference(
        answer_of={q.id: q.answer_id for q in questions},
        question_text={q.id: q.text for q in questions},
    )


def run_query(search: SearchService, item: EvalItem, reference: Reference) -> Outcome:
    hits = search.rank(item.query)
    return Outcome(
        query=item.query,
        expected=frozenset(reference.answer_of[stable_id(text)] for text in item.expected),
        ranked=[hit.answer_id for hit in hits],
        top_score=hits[0].score if hits else 0.0,
        top_question=reference.question_text.get(hits[0].question_id) if hits else None,
    )


def ranking_metrics(outcomes: list[Outcome]) -> dict[str, float]:
    in_domain = [o for o in outcomes if o.in_domain]
    ranks = [o.rank for o in in_domain]
    return {
        "queries": len(in_domain),
        "recall@1": _share(ranks, lambda r: r == 1),
        "recall@3": _share(ranks, lambda r: r is not None and r <= 3),
        "mrr": round(sum(1 / r for r in ranks if r) / len(ranks), 4),
    }


def threshold_point(outcomes: list[Outcome], threshold: float) -> ThresholdPoint:
    in_domain = [o for o in outcomes if o.in_domain]
    rejected_ood = sum(1 for o in outcomes if not o.in_domain and o.top_score < threshold)
    total_ood = sum(1 for o in outcomes if not o.in_domain)
    false_rejections = sum(1 for o in in_domain if o.top_score < threshold)
    precision = rejected_ood / (rejected_ood + false_rejections) if rejected_ood + false_rejections else 0.0
    recall = rejected_ood / total_ood if total_ood else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    answered = sum(1 for o in in_domain if o.top_score >= threshold and o.rank == 1)
    return ThresholdPoint(
        threshold=threshold,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        answered_correctly=round(answered / len(in_domain), 4),
        false_rejections=false_rejections,
        false_acceptances=total_ood - rejected_ood,
    )


def failures(outcomes: list[Outcome], threshold: float) -> dict[str, list[dict[str, object]]]:
    def row(o: Outcome) -> dict[str, object]:
        return {"query": o.query, "score": round(o.top_score, 4), "rank": o.rank, "top_match": o.top_question}

    return {
        "wrong_top1": [row(o) for o in outcomes if o.in_domain and o.rank != 1],
        "false_rejections": [row(o) for o in outcomes if o.in_domain and o.top_score < threshold],
        "false_acceptances": [row(o) for o in outcomes if not o.in_domain and o.top_score >= threshold],
    }


def print_report(ranking: dict[str, float], sweep: list[ThresholdPoint], best: ThresholdPoint) -> None:
    print("\nRanking (in-domain queries)")
    for name, value in ranking.items():
        print(f"  {name:<10} {value}")
    print("\nNo-match decision (positive class = out-of-domain query rejected)")
    print(f"  {'thr':>5} {'prec':>6} {'rec':>6} {'f1':>6} {'answered':>9} {'false_rej':>9} {'false_acc':>9}")
    shown = [p for i, p in enumerate(sweep) if i % TABLE_STEP == 0 or p == best]
    for p in shown:
        marker = "  <- chosen" if p == best else ""
        print(
            f"  {p.threshold:>5.2f} {p.precision:>6.3f} {p.recall:>6.3f} {p.f1:>6.3f} "
            f"{p.answered_correctly:>9.3f} {p.false_rejections:>9} {p.false_acceptances:>9}{marker}"
        )


def run_scenarios(
    conversation: ConversationService, scenarios: list[Scenario], reference: Reference
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for number, scenario in enumerate(scenarios):
        session = f"eval-{number}"
        conversation.reset(session)
        for turn in scenario.turns:
            result = conversation.ask(turn.query, session)
            expected = {reference.answer_of[stable_id(text)] for text in turn.expected}
            correct = result.answer_id in expected if expected else not result.found
            rows.append(
                {
                    "scenario": scenario.name,
                    "query": turn.query,
                    "correct": correct,
                    "matched_question": result.matched_question,
                    "suggestions": result.suggestions,
                    "context_used": result.context_used,
                }
            )
        conversation.reset(session)
    return rows


def print_conversations(rows: list[dict[str, object]]) -> None:
    correct = sum(1 for row in rows if row["correct"])
    print(f"\nConversations: {correct}/{len(rows)} turns correct")
    for row in rows:
        mark = "ok " if row["correct"] else "ERR"
        answer = row["matched_question"] or (
            "clarify: " + str(row["suggestions"]) if row["suggestions"] else "not found"
        )
        print(f"  {mark} [{row['scenario']}] {row['query']!r} -> {answer}")


def _share(ranks: list[int | None], hit: Callable[[int | None], bool]) -> float:
    return round(sum(1 for r in ranks if hit(r)) / len(ranks), 4)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m eval.evaluate")
    parser.add_argument("--dataset", type=Path, default=EVAL_DIR / "dataset.jsonl")
    parser.add_argument("--conversations", type=Path, default=EVAL_DIR / "conversations.jsonl")
    parser.add_argument("--sheet", type=Path, default=Path("data/qa.xlsx"))
    parser.add_argument("--out", type=Path, default=EVAL_DIR / "results")
    args = parser.parse_args()

    configure_logging("WARNING")
    lines = args.dataset.read_text(encoding="utf-8").splitlines()
    items = [EvalItem.model_validate_json(line) for line in lines if line.strip()]
    scenario_lines = args.conversations.read_text(encoding="utf-8").splitlines()
    scenarios = [Scenario.model_validate_json(line) for line in scenario_lines if line.strip()]
    reference = load_reference(args.sheet)
    container = build_container(Settings())
    try:
        outcomes = [run_query(container.search, item, reference) for item in items]
        conversations = run_scenarios(container.conversation, scenarios, reference)
    finally:
        container.close()

    ranking = ranking_metrics(outcomes)
    sweep = [threshold_point(outcomes, t) for t in THRESHOLDS]
    best = max(sweep, key=lambda p: (p.f1, p.answered_correctly))
    print_report(ranking, sweep, best)
    print_conversations(conversations)

    args.out.mkdir(parents=True, exist_ok=True)
    metrics = {"ranking": ranking, "chosen": asdict(best), "sweep": [asdict(p) for p in sweep]}
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (args.out / "failures.json").write_text(
        json.dumps(failures(outcomes, best.threshold), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.out / "conversations.json").write_text(
        json.dumps(conversations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nSaved results to {args.out}/")


if __name__ == "__main__":
    main()

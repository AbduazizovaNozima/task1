"""Tune on development data, then evaluate one frozen candidate on a sealed holdout."""

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.container import build_container
from app.domain.query import word_count
from app.domain.text import stable_id
from app.services.search import SearchService
from eval.evaluate import EvalItem, Reference, load_reference

ROOT = Path(__file__).parent


@dataclass(frozen=True)
class Observation:
    expected: frozenset[str]
    first: str | None
    score: float
    ambiguous: bool
    rank: int | None


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(search: SearchService, path: Path, reference: Reference, settings: Settings) -> list[Observation]:
    observations = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        item = EvalItem.model_validate_json(line)
        hits = search.rank(item.query)
        expected = frozenset(str(reference.answer_of[stable_id(text)]) for text in item.expected)
        ranked = [str(hit.answer_id) for hit in hits]
        ambiguous = (
            len(hits) > 1
            and word_count(item.query) <= settings.ambiguity_max_words
            and hits[0].score - hits[1].score < settings.ambiguity_margin
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


def correct(row: Observation, threshold: float) -> bool:
    found = row.first is not None and row.score >= threshold and not row.ambiguous
    return row.first in row.expected if found else not row.expected


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
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["tune", "holdout"])
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "calibration")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    plan_path = args.out / "frozen_candidate.json"
    manifest = json.loads((ROOT / "holdout_manifest.json").read_text())
    if digest(ROOT / "holdout.jsonl") != manifest["sha256"]:
        raise SystemExit("Frozen holdout hash mismatch")
    settings = Settings()
    reference = load_reference(Path("data/qa.xlsx"))
    if args.stage == "tune" and plan_path.exists():
        raise SystemExit("Candidate already frozen; refusing retuning")
    if args.stage == "holdout" and (args.out / "holdout_summary.json").exists():
        raise SystemExit("Holdout already evaluated; refusing adaptive reuse")
    path = ROOT / ("dev.jsonl" if args.stage == "tune" else "holdout.jsonl")
    container = build_container(settings)
    try:
        rows = collect(container.search, path, reference, settings)
    finally:
        container.close()
    if args.stage == "tune":
        baseline = metrics(rows, settings.match_threshold)
        sweep = [metrics(rows, round(i / 100, 2)) for i in range(30, 91)]
        eligible = [point for point in sweep if point["correct_accepted"] >= 0.95 * baseline["correct_accepted"]]
        chosen = max(
            eligible,
            key=lambda point: (
                point["correct_accepted"] - 2 * point["wrong_accepted"],
                point["correct_accepted"],
                -abs(point["threshold"] - settings.match_threshold),
            ),
        )
        plan = {
            "baseline_threshold": settings.match_threshold,
            "candidate_threshold": chosen["threshold"],
            "selection": (
                "Maximize correct accepted minus twice wrong accepted on DEV, retaining >=95% of "
                "baseline correct accepted; ties favor coverage then closest threshold."
            ),
            "protected_metrics": [
                "decision_accuracy",
                "in_domain_correct_rate",
                "accepted_precision",
                "ood_rejection_f1",
            ],
            "acceptance": (
                "All protected holdout metrics nondecreasing, wrong accepted and OOD false acceptances "
                "nonincreasing, and at least one protected metric strictly better. "
                "One candidate only; otherwise keep baseline."
            ),
            "dev_sha256": digest(ROOT / "dev.jsonl"),
            "holdout_sha256": manifest["sha256"],
        }
        plan_path.write_text(json.dumps(plan, indent=2) + "\n")
        result: dict[str, object] = {"baseline": baseline, "candidate": chosen, "sweep": sweep, "plan": plan}
        (args.out / "dev_summary.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"baseline": baseline, "candidate": chosen, "plan": plan}, indent=2))
    else:
        plan = json.loads(plan_path.read_text())
        if plan["dev_sha256"] != digest(ROOT / "dev.jsonl") or plan["holdout_sha256"] != manifest["sha256"]:
            raise SystemExit("Dataset changed after candidate freeze")
        baseline = metrics(rows, plan["baseline_threshold"])
        candidate = metrics(rows, plan["candidate_threshold"])
        protected = plan["protected_metrics"]
        accepted = (
            all(candidate[key] >= baseline[key] for key in protected)
            and candidate["wrong_accepted"] <= baseline["wrong_accepted"]
            and candidate["false_acceptances"] <= baseline["false_acceptances"]
            and any(candidate[key] > baseline[key] for key in protected)
        )
        improved = sum(
            not correct(row, plan["baseline_threshold"]) and correct(row, plan["candidate_threshold"]) for row in rows
        )
        worsened = sum(
            correct(row, plan["baseline_threshold"]) and not correct(row, plan["candidate_threshold"]) for row in rows
        )
        result = {
            "baseline": baseline,
            "candidate": candidate,
            "accepted": accepted,
            "changed_correctness": {"improved": improved, "worsened": worsened},
            "holdout_sha256": manifest["sha256"],
            "candidate_plan_sha256": digest(plan_path),
        }
        (args.out / "holdout_summary.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        # Deliberately do not write or print holdout per-query predictions/errors.


if __name__ == "__main__":
    main()

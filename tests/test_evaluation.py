import hashlib
import json
from pathlib import Path

import pytest

from eval.evaluate import Observation, metrics


def test_decision_metrics_count_wrong_acceptance_and_ambiguity() -> None:
    rows = [
        Observation(frozenset({"a"}), "a", 0.9, False, 1),
        Observation(frozenset({"b"}), "c", 0.8, False, 2),
        Observation(frozenset(), "a", 0.7, True, None),
        Observation(frozenset(), "a", 0.6, False, None),
    ]
    result = metrics(rows, 0.64)
    assert result["correct_accepted"] == result["wrong_accepted"] == 1
    assert result["false_acceptances"] == result["false_rejections"] == 0
    assert result["decision_accuracy"] == 0.75
    assert result["accepted_precision"] == 0.5
    assert result["ood_rejection_f1"] == 1
    assert result["mrr"] == pytest.approx(0.75)


def test_holdout_is_frozen_and_disjoint_from_development() -> None:
    root = Path(__file__).resolve().parents[1] / "eval"
    manifest = json.loads((root / "holdout_manifest.json").read_text())
    assert hashlib.sha256((root / "holdout.jsonl").read_bytes()).hexdigest() == manifest["sha256"]
    dev = {json.loads(line)["query"] for line in (root / "dev.jsonl").read_text().splitlines()}
    holdout = [json.loads(line) for line in (root / "holdout.jsonl").read_text().splitlines()]
    assert not dev.intersection(row["query"] for row in holdout)
    assert sum(bool(row["expected"]) for row in holdout) == 80
    assert sum(not row["expected"] for row in holdout) == 40

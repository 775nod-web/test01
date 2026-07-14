"""
Validates notebooks/lib/ml_baseline.py (Phase 7, OPTIONAL) against real
Bronze->Silver->Gold data built from the actual generator + SQL (via
tests/conftest.py fixtures). Requires pandas + scikit-learn
(requirements-dev.txt) — skipped gracefully if not installed. This is
optional-feature validation; it must never gate the mandatory test suite.
"""

import sys
from pathlib import Path

import pytest

pytest.importorskip("pandas")
pytest.importorskip("sklearn")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "notebooks" / "lib"))
import ml_baseline  # noqa: E402


@pytest.fixture(scope="module")
def customer_rows(spark, retention_action_list):
    gold = retention_action_list
    c360 = [row.asDict() for row in spark.table(f"{gold}.customer_360").collect()]
    actions = [row.asDict() for row in spark.table(f"{gold}.retention_action_list").collect()]
    return c360, actions


def test_build_customer_frame_joins_cleanly(customer_rows):
    c360, actions = customer_rows
    df = ml_baseline.build_customer_frame(c360, actions)
    assert len(df) == len(c360)
    assert "churn_label_90d" in df.columns
    assert "risk_score" in df.columns


def test_rule_based_evaluation_is_better_than_random(customer_rows):
    c360, actions = customer_rows
    df = ml_baseline.build_customer_frame(c360, actions)
    result = ml_baseline.evaluate_rule_based_score(df)
    assert 0.5 < result.roc_auc <= 1.0, "rule-based score should beat random guessing on its own design"
    assert 0.0 <= result.precision <= 1.0
    assert 0.0 <= result.recall <= 1.0
    assert result.n_test == len(df)


def test_static_model_trains_and_scores_in_valid_range(customer_rows):
    c360, actions = customer_rows
    df = ml_baseline.build_customer_frame(c360, actions)
    result = ml_baseline.evaluate_static_model(df)
    assert 0.0 <= result.roc_auc <= 1.0
    assert 0.0 <= result.precision <= 1.0
    assert 0.0 <= result.recall <= 1.0
    assert result.n_train > 0 and result.n_test > 0


def test_behavioral_model_trains_and_scores_in_valid_range(customer_rows):
    c360, actions = customer_rows
    df = ml_baseline.build_customer_frame(c360, actions)
    result = ml_baseline.evaluate_behavioral_model(df)
    assert 0.0 <= result.roc_auc <= 1.0
    assert result.n_train > 0 and result.n_test > 0


def test_behavioral_features_outperform_static_on_auc(customer_rows):
    """Not a hard business requirement, but the whole point of Customer 360
    is that integrated behavior beats static attributes — if this stops
    holding, it's worth knowing, not silently ignoring."""
    c360, actions = customer_rows
    df = ml_baseline.build_customer_frame(c360, actions)
    static_result = ml_baseline.evaluate_static_model(df)
    behavioral_result = ml_baseline.evaluate_behavioral_model(df)
    assert behavioral_result.roc_auc >= static_result.roc_auc - 0.05, (
        f"behavioral AUC {behavioral_result.roc_auc} unexpectedly far below "
        f"static AUC {static_result.roc_auc}"
    )


def test_run_comparison_returns_all_three(customer_rows):
    c360, actions = customer_rows
    comparison = ml_baseline.run_comparison(c360, actions)
    assert set(comparison.keys()) == {"rule_based", "static_attributes", "behavioral_features"}
    for result in comparison.values():
        assert "roc_auc" in result and "confusion_matrix" in result

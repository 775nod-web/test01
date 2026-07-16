"""DEMO_SPEC.md「データ品質の必須検証」に対応する自動チェック。

コミット済みの artifacts/customer360.json ・ artifacts/predictions.json
（フォールバック用の事前計算済みデータ）そのものを検証する。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts"


@pytest.fixture(scope="module")
def customer360() -> dict:
    with (ARTIFACTS_DIR / "customer360.json").open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def predictions(customer360: dict) -> dict:
    with (ARTIFACTS_DIR / "predictions.json").open(encoding="utf-8") as f:
        return json.load(f)


def test_customer_count_in_common_sense_range(customer360: dict) -> None:
    assert 30 <= len(customer360["customers"]) <= 80


def test_no_negative_amounts(customer360: dict) -> None:
    for customer in customer360["customers"]:
        for service in customer["services"].values():
            assert all(a >= 0 for a in service["monthly_amount"])
        assert all(a >= 0 for a in customer["combined_qr_card"]["monthly_amount"])


def test_no_all_zero_customers(customer360: dict) -> None:
    for customer in customer360["customers"]:
        total = sum(
            sum(service["monthly_amount"]) for service in customer["services"].values()
        )
        assert total > 0, f"{customer['customer_id']} has zero activity across all periods"


def test_no_duplicate_customer_ids(customer360: dict) -> None:
    ids = [c["customer_id"] for c in customer360["customers"]]
    assert len(ids) == len(set(ids))


def test_no_future_dated_activity(customer360: dict) -> None:
    as_of = date.fromisoformat(customer360["as_of_date"])
    for customer in customer360["customers"]:
        for service in customer["services"].values():
            if service["last_used_date"]:
                assert date.fromisoformat(service["last_used_date"]) <= as_of
        for campaign in customer["campaigns"]:
            assert date.fromisoformat(campaign["sent_date"]) <= as_of


def test_last_used_date_consistent_with_activity(customer360: dict) -> None:
    for customer in customer360["customers"]:
        for service in customer["services"].values():
            has_activity = any(a > 0 for a in service["monthly_amount"])
            if service["last_used_date"] is None:
                assert not has_activity
            else:
                assert has_activity


def test_amounts_within_common_sense_yen_range(customer360: dict) -> None:
    for customer in customer360["customers"]:
        for service in customer["services"].values():
            for amount in service["monthly_amount"]:
                assert 0 <= amount <= 500_000


def test_structural_data_quality_report_has_no_violations(customer360: dict) -> None:
    quality = customer360["data_quality"]
    assert quality["negative_amount_found"] is False
    assert quality["all_zero_customer_count"] == 0
    assert quality["duplicate_customer_id_count"] == 0
    assert quality["future_dated_transaction_count"] == 0


def test_risk_band_distribution_includes_all_three_bands(predictions: dict) -> None:
    bands = [p["risk_band"] for p in predictions["predictions"].values()]
    assert set(bands) == {"high", "medium", "low"}
    for band in ("high", "medium", "low"):
        assert bands.count(band) > 0


def test_churn_probability_never_stuck_at_extremes(predictions: dict) -> None:
    for pred in predictions["predictions"].values():
        assert 0.0 < pred["churn_probability"] < 1.0


def test_low_risk_customers_are_not_all_identical(customer360: dict, predictions: dict) -> None:
    low_risk_ids = [
        cid for cid, pred in predictions["predictions"].items() if pred["risk_band"] == "low"
    ]
    assert len(low_risk_ids) > 1
    probabilities = {predictions["predictions"][cid]["churn_probability"] for cid in low_risk_ids}
    assert len(probabilities) > 1


def test_high_risk_customers_show_multi_service_decline_or_service_drop(
    customer360: dict, predictions: dict
) -> None:
    customers_by_id = {c["customer_id"]: c for c in customer360["customers"]}
    high_risk_ids = [
        cid for cid, pred in predictions["predictions"].items() if pred["risk_band"] == "high"
    ]
    assert len(high_risk_ids) > 0

    for cid in high_risk_ids:
        customer = customers_by_id[cid]
        ec_pct = customer["services"].get("ec", {}).get("period_change_pct")
        payment_pct = customer["combined_qr_card"].get("period_change_pct")
        service_dropped = customer["previous_service_count"] > customer["service_count"]
        has_decline_signal = (ec_pct is not None and ec_pct < 0) or (
            payment_pct is not None and payment_pct < 0
        )
        assert has_decline_signal or service_dropped, f"{cid} has no visible decline signal"


def test_prediction_reasons_reference_actual_customer_data(
    customer360: dict, predictions: dict
) -> None:
    customers_by_id = {c["customer_id"]: c for c in customer360["customers"]}
    for cid, pred in predictions["predictions"].items():
        assert 1 <= len(pred["reasons"]) <= 3
        customer = customers_by_id[cid]
        for reason in pred["reasons"]:
            if "ECの直近期間の購入額が前期比" in reason:
                ec_pct = customer["services"]["ec"]["period_change_pct"]
                assert f"{ec_pct:.0f}%" in reason


def test_data_generation_metadata_present(customer360: dict, predictions: dict) -> None:
    assert customer360["generated_at"]
    assert predictions["generated_at"]
    assert predictions["model_version"]
    for pred in predictions["predictions"].values():
        assert pred["model_version"] == predictions["model_version"]
        assert pred["inference_at"]
        # 推論日時はISO8601としてパースできること
        datetime.fromisoformat(pred["inference_at"])

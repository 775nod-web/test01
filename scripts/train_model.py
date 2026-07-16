"""休眠リスクの予測モデル学習と、事前計算済み予測の生成（Layer 2）。

ラベル生成ルール:
    実際の解約フラグは存在しないため（PoC合成データ）、以下の決定論的なルールで
    「経済的な休眠傾向スコア」を顧客ごとに算出し、それを確率として二値ラベルを
    サンプリングして教師データとする（固定シードで再現可能）。

    dormancy_score =
          0.25 * EC利用額の前期比低下（-50%以上の低下で成分1.0に飽和）
        + 0.30 * QR・カード合算利用額の前期比低下（-60%以上の低下で成分1.0に飽和）
        + 0.25 * 利用サービス数の減少（2サービス減少で成分1.0に飽和）
        + 0.20 * 直近利用からの経過日数（90日以上で成分1.0に飽和）
        - 0.07 * 直近施策への反応が「反応あり」の場合
        + 0.03 * 「退会・解約に関する相談」の問い合わせがある場合

ラベル自体はロジスティック回帰の入力特徴量（各成分の元になった生データ）には
含めず、上記スコアを成功確率とみなしたベルヌーイ試行でサンプリングする。
モデルは生データ特徴量からこのラベルを再構成するため、単純な恒等学習にはならない。

モデル方式:
    scikit-learnのLogisticRegression（標準化した数値特徴量）。
    小規模合成データでの評価値はPoCの参考値であり、本番精度を示すものではない。

出力:
    artifacts/predictions.json    顧客別の休眠確率・リスク帯・理由・モデルバージョン・推論日時
    artifacts/model_metadata.json モデルの版・アルゴリズム・学習条件・評価値（参考値）

実行方法:
    pip install -r scripts/requirements-scripts.txt
    python scripts/train_model.py

前提:
    scripts/prepare_customer360.py を先に実行し、artifacts/customer360.json が存在すること。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT_DIR / "artifacts"

SEED = 42
MODEL_VERSION = "logreg-v1-2026.07"

RISK_HIGH_THRESHOLD = 0.66
RISK_LOW_THRESHOLD = 0.34
PROBABILITY_FLOOR = 0.03
PROBABILITY_CEILING = 0.97

FEATURE_NAMES = [
    "ec_decline",
    "payment_decline",
    "service_drop",
    "recency",
    "positive_campaign_response",
    "cancellation_inquiry",
]


def clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def cumulative_change_pct(monthly_amount: list[float]) -> Optional[float]:
    """直近期間 vs 最初期間の累積変化率。緩やかな複数期間の低下傾向をとらえるために使う。"""
    if not monthly_amount or monthly_amount[0] <= 0:
        return None
    return round((monthly_amount[-1] - monthly_amount[0]) / monthly_amount[0] * 100, 1)


def compute_components(customer: dict) -> dict:
    services = customer["services"]

    # 表示用の「前期比」（直近2期間の変化）はDEMO_SPECの文言に合わせて別途保持する。
    ec_pct = services.get("ec", {}).get("period_change_pct")
    payment_pct = customer["combined_qr_card"].get("period_change_pct")

    # スコア算出には、単月のブレに左右されにくい「累積変化率」（最初期間→直近期間）を使う。
    ec_cumulative_pct = cumulative_change_pct(services.get("ec", {}).get("monthly_amount", []))
    ec_decline = (
        clip01(-(ec_cumulative_pct) / 50) if ec_cumulative_pct is not None and ec_cumulative_pct < 0 else 0.0
    )

    payment_cumulative_pct = cumulative_change_pct(customer["combined_qr_card"].get("monthly_amount", []))
    payment_decline = (
        clip01(-(payment_cumulative_pct) / 60)
        if payment_cumulative_pct is not None and payment_cumulative_pct < 0
        else 0.0
    )

    service_drop_count = max(0, customer["previous_service_count"] - customer["service_count"])
    service_drop = clip01(service_drop_count / 2)

    days_candidates = [
        s["days_since_last_used"]
        for s in services.values()
        if s.get("days_since_last_used") is not None
    ]
    days_since_last_used = min(days_candidates) if days_candidates else 999
    recency = clip01(days_since_last_used / 90)

    recent_campaigns = customer["campaigns"][:2]
    positive_campaign_response = 1.0 if any(c["response"] == "反応あり" for c in recent_campaigns) else 0.0

    cancellation_inquiry = (
        1.0 if "退会・解約に関する相談" in customer["support_summary"]["recent_categories"] else 0.0
    )

    return {
        "ec_decline": ec_decline,
        "payment_decline": payment_decline,
        "service_drop": service_drop,
        "recency": recency,
        "positive_campaign_response": positive_campaign_response,
        "cancellation_inquiry": cancellation_inquiry,
        "ec_pct": ec_pct,
        "payment_pct": payment_pct,
        "service_drop_count": service_drop_count,
        "days_since_last_used": days_since_last_used,
    }


def compute_dormancy_score(components: dict) -> float:
    score = (
        0.25 * components["ec_decline"]
        + 0.30 * components["payment_decline"]
        + 0.25 * components["service_drop"]
        + 0.20 * components["recency"]
        - 0.07 * components["positive_campaign_response"]
        + 0.03 * components["cancellation_inquiry"]
    )
    return clip01(score)


def build_reasons(components: dict) -> list[str]:
    """理由は compute_dormancy_score と同じ重みで寄与度を算出し、
    実際にリスクを押し上げている要因が上位に来るようにする（数値と理由の矛盾を防ぐ）。"""
    risk_candidates: list[tuple[float, str]] = []

    ec_pct = components["ec_pct"]
    if ec_pct is not None and ec_pct <= -10:
        risk_candidates.append(
            (0.25 * components["ec_decline"], f"ECの直近期間の購入額が前期比{ec_pct:.0f}%低下しています")
        )

    payment_pct = components["payment_pct"]
    if payment_pct is not None and payment_pct <= -10:
        risk_candidates.append(
            (
                0.30 * components["payment_decline"],
                f"QR決済・カードの利用額が前期比{payment_pct:.0f}%低下しています",
            )
        )

    if components["service_drop_count"] >= 1:
        risk_candidates.append(
            (
                0.25 * components["service_drop"],
                f"利用サービス数が減少しています（{components['service_drop_count']}サービス減）",
            )
        )

    if components["days_since_last_used"] >= 45:
        risk_candidates.append(
            (
                0.20 * components["recency"],
                f"直近{int(components['days_since_last_used'])}日間、目立った利用が確認できません",
            )
        )

    if components["cancellation_inquiry"] >= 1:
        risk_candidates.append((0.03, "退会・解約に関する問い合わせ履歴があります"))

    risk_candidates.sort(key=lambda c: c[0], reverse=True)
    candidates = list(risk_candidates)

    # リスク要因だけで3件に満たない場合、安定・良好を示す理由で補う。
    if len(candidates) < 3:
        if ec_pct is not None and ec_pct > 0:
            candidates.append((0.05, "ECの購入額が前期比で増加しており、利用は安定しています"))
        if payment_pct is not None and payment_pct > 0:
            candidates.append((0.05, "QR決済・カードの利用額が前期比で増加しています"))
        if components["positive_campaign_response"] >= 1:
            candidates.append((0.02, "直近の施策への反応が確認できています"))

    if not candidates:
        candidates.append((0.0, "直近期間の利用状況におおきな変化は見られません"))
    return [text for _, text in candidates[:3]]


def risk_band_for(probability: float) -> str:
    if probability >= RISK_HIGH_THRESHOLD:
        return "high"
    if probability < RISK_LOW_THRESHOLD:
        return "low"
    return "medium"


RISK_BAND_LABEL_JA = {"high": "高", "medium": "中", "low": "低"}


def main() -> None:
    customer360_path = ARTIFACTS_DIR / "customer360.json"
    with customer360_path.open(encoding="utf-8") as f:
        customer360 = json.load(f)

    customers = customer360["customers"]
    components_by_id = {c["customer_id"]: compute_components(c) for c in customers}
    scores_by_id = {cid: compute_dormancy_score(comp) for cid, comp in components_by_id.items()}

    rng = np.random.RandomState(SEED)
    customer_ids = [c["customer_id"] for c in customers]
    labels = {cid: int(rng.random_sample() < scores_by_id[cid]) for cid in customer_ids}

    X = np.array([[components_by_id[cid][name] for name in FEATURE_NAMES] for cid in customer_ids])
    y = np.array([labels[cid] for cid in customer_ids])

    X_train, X_test, y_train, y_test, ids_train, ids_test = train_test_split(
        X, y, customer_ids, test_size=0.25, random_state=SEED, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    X_all_scaled = scaler.transform(X)

    model = LogisticRegression(class_weight="balanced", random_state=SEED)
    model.fit(X_train_scaled, y_train)

    y_pred_test = model.predict(X_test_scaled)
    y_proba_test = model.predict_proba(X_test_scaled)[:, 1]

    evaluation = {
        "accuracy": round(float(accuracy_score(y_test, y_pred_test)), 3),
        "precision": round(float(precision_score(y_test, y_pred_test, zero_division=0)), 3),
        "recall": round(float(recall_score(y_test, y_pred_test, zero_division=0)), 3),
        "roc_auc": round(float(roc_auc_score(y_test, y_proba_test)), 3)
        if len(set(y_test)) > 1
        else None,
        "note": "小規模な合成データ（PoC）上の参考値であり、本番精度を示すものではない。",
    }

    all_proba = model.predict_proba(X_all_scaled)[:, 1]

    inference_at = datetime.now(timezone.utc).isoformat()
    predictions: dict[str, dict] = {}
    risk_band_counts = {"high": 0, "medium": 0, "low": 0}

    for cid, proba in zip(customer_ids, all_proba):
        clipped = float(min(PROBABILITY_CEILING, max(PROBABILITY_FLOOR, proba)))
        risk_band = risk_band_for(clipped)
        risk_band_counts[risk_band] += 1
        reasons = build_reasons(components_by_id[cid])
        predictions[cid] = {
            "churn_probability": round(clipped, 3),
            "risk_band": risk_band,
            "risk_band_label": RISK_BAND_LABEL_JA[risk_band],
            "reasons": reasons,
            "model_version": MODEL_VERSION,
            "inference_at": inference_at,
        }

    # --- モデル出力に対するデータ品質チェック ---
    violations: list[str] = []

    for band in ("high", "medium", "low"):
        if risk_band_counts[band] == 0:
            violations.append(f"リスク帯'{band}'に該当する顧客が0人です。")

    for cid, pred in predictions.items():
        if pred["churn_probability"] <= 0.0 or pred["churn_probability"] >= 1.0:
            violations.append(f"{cid}の休眠確率が0または1に張り付いています。")

    high_risk_ids = [cid for cid, p in predictions.items() if p["risk_band"] == "high"]
    for cid in high_risk_ids:
        comp = components_by_id[cid]
        has_decline_signal = (
            (comp["ec_pct"] is not None and comp["ec_pct"] < 0)
            or (comp["payment_pct"] is not None and comp["payment_pct"] < 0)
            or comp["service_drop_count"] >= 1
        )
        if not has_decline_signal:
            violations.append(f"高リスク顧客{cid}に利用低下の兆候が見られません。")

    low_risk_probs = [predictions[cid]["churn_probability"] for cid in customer_ids if predictions[cid]["risk_band"] == "low"]
    if len(low_risk_probs) > 1 and len(set(low_risk_probs)) == 1:
        violations.append("低リスク顧客の休眠確率が全員同一です。")

    if violations:
        print("モデル出力のデータ品質チェックに失敗しました:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        sys.exit(1)

    predictions_output = {
        "model_version": MODEL_VERSION,
        "generated_at": inference_at,
        "predictions": predictions,
    }

    model_metadata = {
        "model_version": MODEL_VERSION,
        "algorithm": "LogisticRegression（scikit-learn、標準化済み数値特徴量）",
        "trained_at": inference_at,
        "feature_list": FEATURE_NAMES,
        "label_rule_summary": (
            "EC/QR・カード利用額の前期比低下、利用サービス数の減少、直近利用からの経過日数を"
            "重み付け合成したスコアを成功確率としたベルヌーイ試行でラベルを生成し、"
            "そのラベルを特徴量から再構成するようロジスティック回帰を学習した。"
        ),
        "train_size": len(ids_train),
        "test_size": len(ids_test),
        "risk_band_thresholds": {"high": RISK_HIGH_THRESHOLD, "low": RISK_LOW_THRESHOLD},
        "risk_band_distribution": risk_band_counts,
        "evaluation": evaluation,
        "model_mode": "precomputed",
    }

    with (ARTIFACTS_DIR / "predictions.json").open("w", encoding="utf-8") as f:
        json.dump(predictions_output, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with (ARTIFACTS_DIR / "model_metadata.json").open("w", encoding="utf-8") as f:
        json.dump(model_metadata, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("予測結果を生成しました: artifacts/predictions.json")
    print("モデルメタデータを生成しました: artifacts/model_metadata.json")
    print(f"  リスク帯分布: 高{risk_band_counts['high']} / 中{risk_band_counts['medium']} / 低{risk_band_counts['low']}")
    print(f"  評価（参考値）: {evaluation}")


if __name__ == "__main__":
    main()

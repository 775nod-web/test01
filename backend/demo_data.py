"""不正対策デモ(Fraud Decision Center)の合成データと集計ロジック。

すべて架空の合成データであり、実際の取引・顧客情報は含まれない。
数値は日付文字列をシードとした決定論的な疑似乱数で生成しており、
同一条件(シナリオ・期間・チャネル)であれば常に同じ結果を返す。
Spark・SQL・外部APIなど、固定データ以外の処理系には依存しない。
"""
from __future__ import annotations

import random
import statistics
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from backend.models import (
    AiFactor,
    AuditLogEntry,
    BehaviorComparisonRow,
    CaseDetail,
    CaseListResponse,
    CaseSummary,
    Channel,
    ChannelLabel,
    DashboardFilters,
    DashboardResponse,
    HighRiskTransactionRow,
    InvestigationQueueSummary,
    InvestigationResult,
    KpiValue,
    Last7DaysSummary,
    LossSeriesPoint,
    Period,
    Priority,
    RateSeriesPoint,
    RelatedInfo,
    RiskDistributionBand,
    RiskFactor,
    Scenario,
    ScenarioComparison,
    ScenarioComparisonMetrics,
    Status,
    TimelineEntry,
)

JST = timezone(timedelta(hours=9))
REPRESENTATIVE_CASE_ID = "TXN-100123"
MODEL_VERSION = "FraudScore-v2.3(デモ)"

CHANNEL_QUERY_TO_LABEL: Dict[Channel, Optional[ChannelLabel]] = {
    "all": None,
    "mobile": "モバイル決済",
    "debit": "デビットカード",
}


def _now() -> datetime:
    return datetime.now(JST)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y/%m/%d %H:%M") + " (JST)"


def _recent_at(hour: int, minute: int, days_ago: int = 0) -> datetime:
    """常に「現在時刻より過去」になるよう、直近の該当時刻を返す。"""
    now = _now()
    base_date = (now - timedelta(days=days_ago)).date()
    candidate = datetime(base_date.year, base_date.month, base_date.day, hour, minute, tzinfo=JST)
    if candidate > now:
        candidate -= timedelta(days=1)
    return candidate


# ─────────────────────────────────────────────
# 日次集計の合成データ(ダッシュボード用)
# ─────────────────────────────────────────────

CHANNEL_FRACTIONS: Dict[Channel, float] = {"all": 1.0, "mobile": 0.62, "debit": 0.38}

RULES_AVG_INVESTIGATION_MINUTES = 18.4
HYBRID_AVG_INVESTIGATION_MINUTES = 11.2

NORMAL_BAND_SHARE = {
    "rules": {"低": 0.86, "中": 0.11, "高": 0.03},
    "hybrid": {"低": 0.90, "中": 0.08, "高": 0.02},
}
FRAUD_BAND_SHARE = {
    "rules": {"低": 0.05, "中": 0.18, "高": 0.77},
    "hybrid": {"低": 0.03, "中": 0.12, "高": 0.85},
}


def _daily_base(iso_date: str) -> dict:
    rng = random.Random(f"vol-{iso_date}")
    weekday = datetime.fromisoformat(iso_date).weekday()
    weekend_bonus = 1.12 if weekday >= 5 else 1.0
    total_transactions = int(rng.uniform(2800, 3400) * weekend_bonus)
    avg_amount = rng.uniform(7800, 9000)
    total_amount = total_transactions * avg_amount
    actual_fraud_rate = rng.uniform(0.0028, 0.0045)
    actual_fraud_count = max(1, round(total_transactions * actual_fraud_rate))
    fraud_avg_amount = rng.uniform(38000, 55000)
    actual_fraud_amount = actual_fraud_count * fraud_avg_amount
    return {
        "total_transactions": total_transactions,
        "total_amount": total_amount,
        "actual_fraud_count": actual_fraud_count,
        "actual_fraud_amount": actual_fraud_amount,
    }


def _scenario_day_metrics(iso_date: str, scenario: Scenario) -> dict:
    rng = random.Random(f"{scenario}-{iso_date}")
    if scenario == "rules":
        capture_rate = rng.uniform(0.78, 0.86)
        normal_approval_rate = rng.uniform(0.948, 0.968)
        false_positive_rate = rng.uniform(0.026, 0.036)
        step_up_rate = rng.uniform(0.030, 0.045)
        detect_minutes = rng.uniform(3.6, 6.2)
    else:
        capture_rate = rng.uniform(0.80, 0.89)
        normal_approval_rate = rng.uniform(0.962, 0.982)
        false_positive_rate = rng.uniform(0.013, 0.023)
        step_up_rate = rng.uniform(0.055, 0.078)
        detect_minutes = rng.uniform(0.7, 1.7)
    return {
        "capture_rate": capture_rate,
        "normal_approval_rate": normal_approval_rate,
        "false_positive_rate": false_positive_rate,
        "step_up_rate": step_up_rate,
        "detect_minutes": detect_minutes,
    }


def _daily_dates(n: int) -> List[str]:
    today = _now().date()
    return [(today - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def _window_dates(period: Period) -> tuple[List[str], List[str]]:
    days = 7 if period == "7d" else 30
    all_dates = _daily_dates(days * 2)
    return all_dates[-days:], all_dates[: days]


def _aggregate(dates: List[str], scenario: Scenario, channel: Channel) -> dict:
    channel_frac = CHANNEL_FRACTIONS[channel]
    total_transactions = 0
    total_amount = 0.0
    actual_fraud_count = 0
    actual_fraud_amount = 0.0
    confirmed_fraud_count = 0
    prevented_loss = 0.0
    fraud_loss = 0.0
    legit_count = 0
    approved_legit_count = 0
    false_positive_count = 0
    step_up_count = 0
    detect_minutes: List[float] = []
    per_day: List[dict] = []

    for d in dates:
        base = _daily_base(d)
        metrics = _scenario_day_metrics(d, scenario)

        tt = round(base["total_transactions"] * channel_frac)
        ta = base["total_amount"] * channel_frac
        afc = round(base["actual_fraud_count"] * channel_frac) or (1 if base["actual_fraud_count"] else 0)
        afa = base["actual_fraud_amount"] * channel_frac
        cfc = round(afc * metrics["capture_rate"])
        pl = afa * metrics["capture_rate"]
        fl = afa - pl
        lc = max(tt - afc, 0)
        alc = round(lc * metrics["normal_approval_rate"])
        fpc = round(lc * metrics["false_positive_rate"])
        suc = round(lc * metrics["step_up_rate"])

        total_transactions += tt
        total_amount += ta
        actual_fraud_count += afc
        actual_fraud_amount += afa
        confirmed_fraud_count += cfc
        prevented_loss += pl
        fraud_loss += fl
        legit_count += lc
        approved_legit_count += alc
        false_positive_count += fpc
        step_up_count += suc
        detect_minutes.append(metrics["detect_minutes"])

        per_day.append(
            {
                "date": d,
                "fraud_rate": (cfc / tt) if tt else 0.0,
                "normal_approval_rate": (alc / lc) if lc else 1.0,
                "fraud_loss_amount": fl,
                "prevented_loss_amount": pl,
            }
        )

    return {
        "total_transactions": total_transactions,
        "total_amount": total_amount,
        "actual_fraud_count": actual_fraud_count,
        "actual_fraud_amount": actual_fraud_amount,
        "confirmed_fraud_count": confirmed_fraud_count,
        "prevented_loss": prevented_loss,
        "fraud_loss": fraud_loss,
        "legit_count": legit_count,
        "approved_legit_count": approved_legit_count,
        "false_positive_count": false_positive_count,
        "step_up_count": step_up_count,
        "avg_detect_minutes": statistics.mean(detect_minutes) if detect_minutes else 0.0,
        "per_day": per_day,
    }


def _risk_distribution(agg: dict, scenario: Scenario) -> Dict[str, RiskDistributionBand]:
    bands: Dict[str, RiskDistributionBand] = {}
    for band in ("低", "中", "高"):
        normal_count = round(agg["legit_count"] * NORMAL_BAND_SHARE[scenario][band])
        fraud_count = round(agg["actual_fraud_count"] * FRAUD_BAND_SHARE[scenario][band])
        bands[band] = RiskDistributionBand(band=band, normal_count=normal_count, fraud_count=fraud_count)
    return bands


def _scenario_comparison_metrics(agg: dict, scenario: Scenario) -> ScenarioComparisonMetrics:
    avg_minutes = RULES_AVG_INVESTIGATION_MINUTES if scenario == "rules" else HYBRID_AVG_INVESTIGATION_MINUTES
    return ScenarioComparisonMetrics(
        fraud_capture_rate=(agg["confirmed_fraud_count"] / agg["actual_fraud_count"]) if agg["actual_fraud_count"] else 0.0,
        normal_approval_rate=(agg["approved_legit_count"] / agg["legit_count"]) if agg["legit_count"] else 0.0,
        false_positive_rate=(agg["false_positive_count"] / agg["legit_count"]) if agg["legit_count"] else 0.0,
        prevented_loss_amount=agg["prevented_loss"],
        avg_investigation_time_minutes=avg_minutes,
    )


def build_dashboard(scenario: Scenario, period: Period, channel: Channel) -> DashboardResponse:
    current_dates, previous_dates = _window_dates(period)
    current = _aggregate(current_dates, scenario, channel)
    previous = _aggregate(previous_dates, scenario, channel)

    current_dist = _risk_distribution(current, scenario)
    previous_dist = _risk_distribution(previous, scenario)
    high_risk_count = sum(b.normal_count + b.fraud_count for b in [current_dist["高"]])
    high_risk_count_prev = sum(b.normal_count + b.fraud_count for b in [previous_dist["高"]])

    confirmed_fraud_rate = (current["confirmed_fraud_count"] / current["total_transactions"]) if current["total_transactions"] else 0.0
    confirmed_fraud_rate_prev = (previous["confirmed_fraud_count"] / previous["total_transactions"]) if previous["total_transactions"] else 0.0
    normal_approval_rate = (current["approved_legit_count"] / current["legit_count"]) if current["legit_count"] else 0.0
    normal_approval_rate_prev = (previous["approved_legit_count"] / previous["legit_count"]) if previous["legit_count"] else 0.0
    false_positive_rate = (current["false_positive_count"] / current["legit_count"]) if current["legit_count"] else 0.0
    false_positive_rate_prev = (previous["false_positive_count"] / previous["legit_count"]) if previous["legit_count"] else 0.0
    step_up_rate = (current["step_up_count"] / current["legit_count"]) if current["legit_count"] else 0.0
    step_up_rate_prev = (previous["step_up_count"] / previous["legit_count"]) if previous["legit_count"] else 0.0

    active_cases = [c for c in _runtime_cases() if _matches_channel(c, channel)]
    pending_count = sum(1 for c in active_cases if c["status"] == "未着手")
    in_progress_count = sum(1 for c in active_cases if c["status"] == "調査中")
    completed_count = sum(1 for c in active_cases if c["status"] == "完了")
    pending_investigation_count = pending_count + in_progress_count

    jitter = random.Random(f"prev-{scenario}-{period}-{channel}")
    pending_prev = max(0, pending_investigation_count + jitter.randint(-4, 6))
    avg_investigation_minutes = RULES_AVG_INVESTIGATION_MINUTES if scenario == "rules" else HYBRID_AVG_INVESTIGATION_MINUTES
    avg_investigation_minutes_prev = avg_investigation_minutes + jitter.uniform(-1.2, 2.0)

    kpis = [
        KpiValue(
            key="total_transactions", label="総取引件数", value=current["total_transactions"], unit="count",
            description="選択期間・チャネルにおける全取引件数です。",
            previous_value=previous["total_transactions"], delta=current["total_transactions"] - previous["total_transactions"],
        ),
        KpiValue(
            key="total_amount", label="総取引金額", value=current["total_amount"], unit="jpy",
            description="選択期間・チャネルにおける取引金額の合計です。",
            previous_value=previous["total_amount"], delta=current["total_amount"] - previous["total_amount"],
        ),
        KpiValue(
            key="high_risk_count", label="高リスク取引件数", value=high_risk_count, unit="count",
            description="リスクスコアが「高」帯に分類された取引の件数です。",
            previous_value=high_risk_count_prev, delta=high_risk_count - high_risk_count_prev,
        ),
        KpiValue(
            key="prevented_loss_amount", label="推定防止損失額", value=current["prevented_loss"], unit="jpy",
            description="不正取引のうち、検知・対応により被害を防げたと推定される金額です。",
            previous_value=previous["prevented_loss"], delta=current["prevented_loss"] - previous["prevented_loss"],
            is_primary=True,
        ),
        KpiValue(
            key="confirmed_fraud_rate", label="確定不正率", value=confirmed_fraud_rate, unit="percent",
            description="全取引に占める、調査により不正と確定した取引の割合です。",
            previous_value=confirmed_fraud_rate_prev, delta=confirmed_fraud_rate - confirmed_fraud_rate_prev,
        ),
        KpiValue(
            key="normal_approval_rate", label="正常取引承認率", value=normal_approval_rate, unit="percent",
            description="正常な取引のうち、問題なく承認された割合です。高いほど顧客体験を守れています。",
            previous_value=normal_approval_rate_prev, delta=normal_approval_rate - normal_approval_rate_prev,
            is_primary=True,
        ),
        KpiValue(
            key="false_positive_rate", label="誤検知率", value=false_positive_rate, unit="percent",
            description="正常な取引を誤って高リスクと判定してしまった割合です。低いほど良好です。",
            previous_value=false_positive_rate_prev, delta=false_positive_rate - false_positive_rate_prev,
            is_primary=True,
        ),
        KpiValue(
            key="step_up_auth_rate", label="追加認証率", value=step_up_rate, unit="percent",
            description="正常な取引のうち、追加認証(ステップアップ認証)を求めた割合です。",
            previous_value=step_up_rate_prev, delta=step_up_rate - step_up_rate_prev,
        ),
        KpiValue(
            key="avg_detection_time_minutes", label="平均検知時間", value=current["avg_detect_minutes"], unit="minutes",
            description="取引発生からリスク検知までの平均所要時間です。",
            previous_value=previous["avg_detect_minutes"], delta=current["avg_detect_minutes"] - previous["avg_detect_minutes"],
            is_primary=True,
        ),
        KpiValue(
            key="pending_investigation_count", label="調査待ち件数", value=pending_investigation_count, unit="count",
            description="現在調査担当者の対応待ち、または調査中のケース件数です(セッション内の状態)。",
            previous_value=pending_prev, delta=pending_investigation_count - pending_prev,
        ),
        KpiValue(
            key="avg_investigation_time_minutes", label="平均調査時間", value=avg_investigation_minutes, unit="minutes",
            description="調査担当者が1件のケースを調査するのに要する平均時間です。",
            previous_value=avg_investigation_minutes_prev, delta=avg_investigation_minutes - avg_investigation_minutes_prev,
        ),
    ]

    rules_agg = current if scenario == "rules" else _aggregate(current_dates, "rules", channel)
    hybrid_agg = current if scenario == "hybrid" else _aggregate(current_dates, "hybrid", channel)
    comparison = ScenarioComparison(
        rules=_scenario_comparison_metrics(rules_agg, "rules"),
        hybrid=_scenario_comparison_metrics(hybrid_agg, "hybrid"),
        message=(
            "同程度以上の不正捕捉を維持しながら、正常取引の拒否と調査負荷を抑えられる可能性を示しています。"
            "数値はデモ用であり、実際の効果はPoCで顧客データを用いて検証します。"
        ),
    )

    rate_series = [RateSeriesPoint(date=p["date"], fraud_rate=p["fraud_rate"], normal_approval_rate=p["normal_approval_rate"]) for p in current["per_day"]]
    loss_series = [LossSeriesPoint(date=p["date"], fraud_loss_amount=p["fraud_loss_amount"], prevented_loss_amount=p["prevented_loss_amount"]) for p in current["per_day"]]
    risk_distribution = [current_dist["低"], current_dist["中"], current_dist["高"]]

    high_risk_rows = [
        HighRiskTransactionRow(
            transaction_id=c["transaction_id"], priority=c["priority"], risk_score=c["risk_score"],
            recommended_action=c["recommended_action"], amount=c["amount"], merchant=c["merchant"],
            transaction_datetime=_fmt(c["transaction_datetime"]), status=c["status"],
        )
        for c in _sorted_cases_for_dashboard(active_cases)[:8]
    ]

    by_priority: Dict[Priority, int] = {"最優先": 0, "高": 0, "中": 0, "低": 0}
    for c in active_cases:
        if c["status"] != "完了":
            by_priority[c["priority"]] += 1

    queue = InvestigationQueueSummary(
        pending_count=pending_count, in_progress_count=in_progress_count,
        completed_count=completed_count, by_priority=by_priority,
    )

    return DashboardResponse(
        filters=DashboardFilters(scenario=scenario, period=period, channel=channel),
        kpis=kpis,
        comparison=comparison,
        rate_series=rate_series,
        loss_series=loss_series,
        risk_distribution=risk_distribution,
        high_risk_transactions=high_risk_rows,
        investigation_queue=queue,
        data_updated_at=_fmt(_now()),
    )


def _matches_channel(case: dict, channel: Channel) -> bool:
    label = CHANNEL_QUERY_TO_LABEL[channel]
    return label is None or case["channel"] == label


def _sorted_cases_for_dashboard(cases: List[dict]) -> List[dict]:
    def sort_key(c: dict) -> tuple:
        return (0 if c["transaction_id"] == REPRESENTATIVE_CASE_ID else 1, -c["risk_score"])

    return sorted(cases, key=sort_key)


# ─────────────────────────────────────────────
# 調査ケースの合成データ
# ─────────────────────────────────────────────

def _rf(name: str, observed: str, normal: str, contribution: str, desc: str) -> RiskFactor:
    return RiskFactor(name=name, observed_value=observed, normal_value=normal, contribution=contribution, description=desc)


def _ai(name: str, weight: float, desc: str) -> AiFactor:
    return AiFactor(name=name, weight=weight, description=desc)


def _tl(dt: datetime, merchant: str, amount: float, region: str, device: str, judgement: str, status: str) -> TimelineEntry:
    return TimelineEntry(time=dt.strftime("%H:%M"), merchant=merchant, amount=amount, region=region, device=device, judgement=judgement, status=status)


def _audit(dt: datetime, actor: str, action: str) -> AuditLogEntry:
    return AuditLogEntry(timestamp=_fmt(dt), actor=actor, action=action)


def _build_case_seed() -> List[dict]:
    tx_time = _recent_at(2, 14)
    cases: List[dict] = [
        dict(
            transaction_id="TXN-100123", risk_score=0.92, recommended_action="保留", priority="最優先",
            status="調査中", amount=98000, transaction_datetime=tx_time, merchant="サンライズマート大阪店",
            customer_id="CUST-8732", card_last4="4471", region="大阪", channel="モバイル決済",
            related_transaction_count=4,
            detection_summary="新規端末・深夜帯・短時間連続取引など複数の要因が重なっています。",
            risk_factors=[
                _rf("新規端末", "新規端末", "登録済み端末", "高", "過去に利用実績のない端末からの取引です。"),
                _rf("通常と異なる深夜帯", "02:14", "07:00〜23:00", "高", "顧客の通常利用時間帯から大きく外れています。"),
                _rf("15分以内の連続取引", "4回", "0〜1回", "高", "短時間に複数回の取引が発生しています。"),
                _rf("通常利用地域からの乖離", "大阪", "東京近郊", "中", "普段利用しない地域からの取引です。"),
                _rf("過去平均を上回る金額", "¥98,000", "平均 ¥8,400", "中", "直近の平均取引額を大きく上回っています。"),
            ],
            behavior_comparison=[
                BehaviorComparisonRow(item="利用時間帯", current_value="02:14", normal_value="07:00〜23:00"),
                BehaviorComparisonRow(item="端末", current_value="新規端末", normal_value="登録済み端末"),
                BehaviorComparisonRow(item="地域", current_value="大阪", normal_value="東京近郊"),
                BehaviorComparisonRow(item="取引金額", current_value="¥98,000", normal_value="平均 ¥8,400"),
                BehaviorComparisonRow(item="15分以内の回数", current_value="4回", normal_value="0〜1回"),
            ],
            timeline=[
                _tl(tx_time - timedelta(hours=20), "コンビニエンスストア東京丸の内店", 980, "東京近郊", "登録済み端末", "正常", "承認"),
                _tl(tx_time - timedelta(hours=14), "オンライン書店ブックタウン", 3200, "東京近郊", "登録済み端末", "正常", "承認"),
                _tl(tx_time - timedelta(minutes=42), "サンライズマート大阪店", 12000, "大阪", "新規端末", "要確認", "保留"),
                _tl(tx_time - timedelta(minutes=27), "サンライズマート大阪店", 21000, "大阪", "新規端末", "要確認", "保留"),
                _tl(tx_time - timedelta(minutes=9), "サンライズマート大阪店", 34500, "大阪", "新規端末", "要確認", "保留"),
                _tl(tx_time, "サンライズマート大阪店", 98000, "大阪", "新規端末", "要確認", "保留"),
            ],
            last_7_days_summary=Last7DaysSummary(transaction_count=16, total_amount=134800, average_amount=8425, fraud_flagged_count=0),
            related_info=RelatedInfo(
                related_cards=["末尾4471(今回利用)"],
                related_devices=["新規端末(今回使用)", "端末ID:AND-7742(登録済み)"],
                related_accounts=["CUST-8732(本人)"],
                related_merchants=["サンライズマート大阪店", "コンビニエンスストア東京丸の内店", "オンライン書店ブックタウン"],
            ),
            rule_reasons=[
                "深夜帯(00:00〜05:00)の高額取引ルールに該当",
                "同一カードで15分以内に3回以上の取引",
                "新規端末からの初回高額取引",
            ],
            ai_top_factors=[
                _ai("取引時間帯の異常度", 0.34, "通常利用時間帯から大きく外れています。"),
                _ai("端末信頼スコア", 0.28, "初回利用端末で信頼スコアが低い状態です。"),
                _ai("短時間取引頻度", 0.21, "15分以内に複数回の取引が発生しています。"),
                _ai("地理的異常度", 0.17, "普段の利用地域から離れた場所での取引です。"),
            ],
            decision_offset_minutes=6,
            audit_log_extra=[],
        ),
        dict(
            transaction_id="TXN-100088", risk_score=0.88, recommended_action="拒否", priority="最優先",
            status="未着手", amount=156000, transaction_datetime=_recent_at(1, 47, days_ago=1),
            merchant="夜間コンビニエンスNEO渋谷店", customer_id="CUST-4410", card_last4="9013",
            region="東京", channel="デビットカード", related_transaction_count=3,
            detection_summary="新規端末からの深夜高額取引で、短時間に取引額が急増しています。",
            risk_factors=[
                _rf("新規端末", "新規端末", "登録済み端末", "高", "過去に利用実績のない端末からの取引です。"),
                _rf("通常と異なる深夜帯", "01:47", "08:00〜22:00", "高", "顧客の通常利用時間帯から大きく外れています。"),
                _rf("合計利用額の急増", "¥156,000(直近24時間)", "直近7日平均 ¥9,800", "高", "直近24時間の合計利用額が急増しています。"),
            ],
            behavior_comparison=[
                BehaviorComparisonRow(item="利用時間帯", current_value="01:47", normal_value="08:00〜22:00"),
                BehaviorComparisonRow(item="端末", current_value="新規端末", normal_value="登録済み端末"),
                BehaviorComparisonRow(item="取引金額", current_value="¥156,000", normal_value="平均 ¥9,800"),
            ],
            timeline=[
                _tl(_recent_at(1, 47, days_ago=1) - timedelta(hours=5), "駅前ドラッグストア", 1400, "東京", "登録済み端末", "正常", "承認"),
                _tl(_recent_at(1, 47, days_ago=1) - timedelta(minutes=20), "夜間コンビニエンスNEO渋谷店", 64000, "東京", "新規端末", "要確認", "拒否"),
                _tl(_recent_at(1, 47, days_ago=1), "夜間コンビニエンスNEO渋谷店", 156000, "東京", "新規端末", "要確認", "拒否"),
            ],
            last_7_days_summary=Last7DaysSummary(transaction_count=11, total_amount=68200, average_amount=6200, fraud_flagged_count=0),
            related_info=RelatedInfo(
                related_cards=["末尾9013(今回利用)"],
                related_devices=["新規端末(今回使用)"],
                related_accounts=["CUST-4410(本人)"],
                related_merchants=["夜間コンビニエンスNEO渋谷店", "駅前ドラッグストア"],
            ),
            rule_reasons=["深夜帯の高額取引ルールに該当", "直近24時間の利用額急増ルールに該当"],
            ai_top_factors=[
                _ai("端末信頼スコア", 0.31, "初回利用端末で信頼スコアが低い状態です。"),
                _ai("金額急増度", 0.29, "直近の利用額から大きく逸脱しています。"),
                _ai("取引時間帯の異常度", 0.22, "通常利用時間帯から外れています。"),
            ],
            decision_offset_minutes=0,
            audit_log_extra=[],
        ),
        dict(
            transaction_id="TXN-100050", risk_score=0.81, recommended_action="保留", priority="高",
            status="調査中", amount=42000, transaction_datetime=_recent_at(23, 5, days_ago=1),
            merchant="オンライン家電マーケットHAYABUSA", customer_id="CUST-2201", card_last4="5528",
            region="福岡", channel="モバイル決済", related_transaction_count=2,
            detection_summary="初回利用の加盟店での高額なオンライン取引です。",
            risk_factors=[
                _rf("初回利用の加盟店", "初回利用", "利用実績のある加盟店", "中", "これまで利用履歴のない加盟店です。"),
                _rf("過去平均を上回る金額", "¥42,000", "平均 ¥7,600", "中", "直近の平均取引額を上回っています。"),
                _rf("通常と異なる深夜帯", "23:05", "09:00〜22:00", "低", "やや通常利用時間帯から外れています。"),
            ],
            behavior_comparison=[
                BehaviorComparisonRow(item="加盟店", current_value="初回利用", normal_value="利用実績あり"),
                BehaviorComparisonRow(item="取引金額", current_value="¥42,000", normal_value="平均 ¥7,600"),
            ],
            timeline=[
                _tl(_recent_at(23, 5, days_ago=1) - timedelta(hours=3), "オンライン衣料品店FIT", 5400, "福岡", "登録済み端末", "正常", "承認"),
                _tl(_recent_at(23, 5, days_ago=1), "オンライン家電マーケットHAYABUSA", 42000, "福岡", "登録済み端末", "要確認", "保留"),
            ],
            last_7_days_summary=Last7DaysSummary(transaction_count=9, total_amount=41200, average_amount=4580, fraud_flagged_count=0),
            related_info=RelatedInfo(
                related_cards=["末尾5528(今回利用)"],
                related_devices=["端末ID:IOS-3391(登録済み)"],
                related_accounts=["CUST-2201(本人)"],
                related_merchants=["オンライン家電マーケットHAYABUSA", "オンライン衣料品店FIT"],
            ),
            rule_reasons=["初回加盟店での高額取引ルールに該当"],
            ai_top_factors=[
                _ai("加盟店信頼スコア", 0.26, "初回利用の加盟店で実績データが乏しい状態です。"),
                _ai("金額逸脱度", 0.24, "直近の平均利用額から逸脱しています。"),
            ],
            decision_offset_minutes=None,
            audit_log_extra=[],
        ),
        dict(
            transaction_id="TXN-099821", risk_score=0.76, recommended_action="ステップアップ認証", priority="高",
            status="未着手", amount=31000, transaction_datetime=_recent_at(20, 30, days_ago=2),
            merchant="セレクトブティックMIRAI", customer_id="CUST-3352", card_last4="7710",
            region="愛知", channel="デビットカード", related_transaction_count=1,
            detection_summary="登録地域から離れた場所での高額取引です。",
            risk_factors=[
                _rf("通常利用地域からの乖離", "愛知", "神奈川", "中", "普段利用しない地域からの取引です。"),
                _rf("過去平均を上回る金額", "¥31,000", "平均 ¥6,900", "中", "直近の平均取引額を上回っています。"),
                _rf("初回利用の加盟店", "初回利用", "利用実績のある加盟店", "低", "これまで利用履歴のない加盟店です。"),
            ],
            behavior_comparison=[
                BehaviorComparisonRow(item="地域", current_value="愛知", normal_value="神奈川"),
                BehaviorComparisonRow(item="取引金額", current_value="¥31,000", normal_value="平均 ¥6,900"),
            ],
            timeline=[_tl(_recent_at(20, 30, days_ago=2), "セレクトブティックMIRAI", 31000, "愛知", "登録済み端末", "要確認", "ステップアップ認証待ち")],
            last_7_days_summary=Last7DaysSummary(transaction_count=7, total_amount=28300, average_amount=4043, fraud_flagged_count=0),
            related_info=RelatedInfo(
                related_cards=["末尾7710(今回利用)"], related_devices=["端末ID:AND-1102(登録済み)"],
                related_accounts=["CUST-3352(本人)"], related_merchants=["セレクトブティックMIRAI"],
            ),
            rule_reasons=["登録地域外での高額取引ルールに該当"],
            ai_top_factors=[_ai("地理的異常度", 0.27, "普段の利用地域から離れた場所での取引です。")],
            decision_offset_minutes=None,
            audit_log_extra=[],
        ),
        dict(
            transaction_id="TXN-099700", risk_score=0.69, recommended_action="ステップアップ認証", priority="中",
            status="調査中", amount=27500, transaction_datetime=_recent_at(13, 12, days_ago=2),
            merchant="デジタルチケットストアPLAY", customer_id="CUST-6650", card_last4="3387",
            region="北海道", channel="モバイル決済", related_transaction_count=2,
            detection_summary="短時間に同一加盟店での購入が連続しています。",
            risk_factors=[
                _rf("15分以内の連続取引", "2回", "0〜1回", "中", "短時間に複数回の取引が発生しています。"),
                _rf("過去平均を上回る金額", "¥27,500", "平均 ¥5,200", "中", "直近の平均取引額を上回っています。"),
                _rf("初回利用の加盟店", "初回利用", "利用実績のある加盟店", "低", "これまで利用履歴のない加盟店です。"),
            ],
            behavior_comparison=[BehaviorComparisonRow(item="15分以内の回数", current_value="2回", normal_value="0〜1回")],
            timeline=[
                _tl(_recent_at(13, 12, days_ago=2) - timedelta(minutes=10), "デジタルチケットストアPLAY", 14000, "北海道", "登録済み端末", "要確認", "ステップアップ認証待ち"),
                _tl(_recent_at(13, 12, days_ago=2), "デジタルチケットストアPLAY", 13500, "北海道", "登録済み端末", "要確認", "ステップアップ認証待ち"),
            ],
            last_7_days_summary=Last7DaysSummary(transaction_count=12, total_amount=39800, average_amount=3316, fraud_flagged_count=0),
            related_info=RelatedInfo(
                related_cards=["末尾3387(今回利用)"], related_devices=["端末ID:IOS-8820(登録済み)"],
                related_accounts=["CUST-6650(本人)"], related_merchants=["デジタルチケットストアPLAY"],
            ),
            rule_reasons=["短時間連続取引ルールに該当"],
            ai_top_factors=[_ai("短時間取引頻度", 0.22, "短時間に同一加盟店での取引が連続しています。")],
            decision_offset_minutes=None,
            audit_log_extra=[],
        ),
        dict(
            transaction_id="TXN-099650", risk_score=0.58, recommended_action="保留", priority="中",
            status="未着手", amount=19800, transaction_datetime=_recent_at(9, 40, days_ago=3),
            merchant="ホームセンターグリーンフィールド", customer_id="CUST-7793", card_last4="1122",
            region="大阪", channel="デビットカード", related_transaction_count=1,
            detection_summary="平均をやや上回る金額の取引です。",
            risk_factors=[
                _rf("過去平均を上回る金額", "¥19,800", "平均 ¥6,100", "中", "直近の平均取引額を上回っています。"),
                _rf("初回利用の加盟店", "初回利用", "利用実績のある加盟店", "低", "これまで利用履歴のない加盟店です。"),
                _rf("通常と異なる深夜帯", "09:40", "10:00〜21:00", "低", "やや通常利用時間帯から外れています。"),
            ],
            behavior_comparison=[BehaviorComparisonRow(item="取引金額", current_value="¥19,800", normal_value="平均 ¥6,100")],
            timeline=[_tl(_recent_at(9, 40, days_ago=3), "ホームセンターグリーンフィールド", 19800, "大阪", "登録済み端末", "要確認", "保留")],
            last_7_days_summary=Last7DaysSummary(transaction_count=10, total_amount=32400, average_amount=3240, fraud_flagged_count=0),
            related_info=RelatedInfo(
                related_cards=["末尾1122(今回利用)"], related_devices=["端末ID:AND-4471(登録済み)"],
                related_accounts=["CUST-7793(本人)"], related_merchants=["ホームセンターグリーンフィールド"],
            ),
            rule_reasons=["平均利用額超過ルールに該当"],
            ai_top_factors=[_ai("金額逸脱度", 0.18, "直近の平均利用額をやや上回っています。")],
            decision_offset_minutes=None,
            audit_log_extra=[],
        ),
        dict(
            transaction_id="TXN-099500", risk_score=0.94, recommended_action="拒否", priority="最優先",
            status="完了", amount=210000, transaction_datetime=_recent_at(3, 5, days_ago=4),
            merchant="ノーブランド換金ショップEX", customer_id="CUST-1187", card_last4="6604",
            region="沖縄", channel="モバイル決済", related_transaction_count=5,
            detection_summary="深夜帯の高額取引に加え、複数の関連取引が確認されました。",
            risk_factors=[
                _rf("新規端末", "新規端末", "登録済み端末", "高", "過去に利用実績のない端末からの取引です。"),
                _rf("通常と異なる深夜帯", "03:05", "08:00〜23:00", "高", "顧客の通常利用時間帯から大きく外れています。"),
                _rf("15分以内の連続取引", "5回", "0〜1回", "高", "短時間に複数回の取引が発生しています。"),
                _rf("通常利用地域からの乖離", "沖縄", "大阪", "中", "普段利用しない地域からの取引です。"),
            ],
            behavior_comparison=[
                BehaviorComparisonRow(item="利用時間帯", current_value="03:05", normal_value="08:00〜23:00"),
                BehaviorComparisonRow(item="端末", current_value="新規端末", normal_value="登録済み端末"),
                BehaviorComparisonRow(item="地域", current_value="沖縄", normal_value="大阪"),
            ],
            timeline=[
                _tl(_recent_at(3, 5, days_ago=4) - timedelta(minutes=30), "ノーブランド換金ショップEX", 55000, "沖縄", "新規端末", "要確認", "拒否"),
                _tl(_recent_at(3, 5, days_ago=4) - timedelta(minutes=15), "ノーブランド換金ショップEX", 60000, "沖縄", "新規端末", "要確認", "拒否"),
                _tl(_recent_at(3, 5, days_ago=4), "ノーブランド換金ショップEX", 95000, "沖縄", "新規端末", "要確認", "拒否"),
            ],
            last_7_days_summary=Last7DaysSummary(transaction_count=14, total_amount=98700, average_amount=7050, fraud_flagged_count=1),
            related_info=RelatedInfo(
                related_cards=["末尾6604(今回利用)"],
                related_devices=["新規端末(今回使用)"],
                related_accounts=["CUST-1187(本人)"],
                related_merchants=["ノーブランド換金ショップEX"],
            ),
            rule_reasons=["深夜帯の高額取引ルールに該当", "短時間連続取引ルールに該当", "新規端末からの初回高額取引"],
            ai_top_factors=[
                _ai("取引時間帯の異常度", 0.33, "通常利用時間帯から大きく外れています。"),
                _ai("端末信頼スコア", 0.30, "初回利用端末で信頼スコアが低い状態です。"),
                _ai("短時間取引頻度", 0.24, "短時間に複数回の取引が発生しています。"),
            ],
            decision_offset_minutes=95,
            audit_log_extra=[("調査担当者", "調査結果「不正」を登録")],
            investigation_result="不正",
            investigation_memo="複数の加盟店で同一端末からの連続利用を確認。カード会社へ連携済み(デモ表示)。",
        ),
        dict(
            transaction_id="TXN-099400", risk_score=0.87, recommended_action="保留", priority="高",
            status="完了", amount=88000, transaction_datetime=_recent_at(19, 20, days_ago=3),
            merchant="プレミアム家具ストアLUXE", customer_id="CUST-5540", card_last4="2290",
            region="東京", channel="デビットカード", related_transaction_count=1,
            detection_summary="高額取引ですが、事前連絡のある大型家具購入でした。",
            risk_factors=[
                _rf("過去平均を上回る金額", "¥88,000", "平均 ¥9,100", "高", "直近の平均取引額を大きく上回っています。"),
                _rf("初回利用の加盟店", "初回利用", "利用実績のある加盟店", "中", "これまで利用履歴のない加盟店です。"),
                _rf("通常と異なる深夜帯", "19:20", "09:00〜21:00", "低", "通常利用時間帯にほぼ収まっています。"),
            ],
            behavior_comparison=[BehaviorComparisonRow(item="取引金額", current_value="¥88,000", normal_value="平均 ¥9,100")],
            timeline=[_tl(_recent_at(19, 20, days_ago=3), "プレミアム家具ストアLUXE", 88000, "東京", "登録済み端末", "要確認", "保留")],
            last_7_days_summary=Last7DaysSummary(transaction_count=13, total_amount=54200, average_amount=4169, fraud_flagged_count=0),
            related_info=RelatedInfo(
                related_cards=["末尾2290(今回利用)"], related_devices=["端末ID:IOS-2201(登録済み)"],
                related_accounts=["CUST-5540(本人)"], related_merchants=["プレミアム家具ストアLUXE"],
            ),
            rule_reasons=["平均利用額超過ルールに該当"],
            ai_top_factors=[_ai("金額逸脱度", 0.29, "直近の平均利用額を大きく上回っています。")],
            decision_offset_minutes=180,
            audit_log_extra=[("調査担当者", "調査結果「正常」を登録")],
            investigation_result="正常",
            investigation_memo="配送先住所と一致する大型家具の購入。本人へ電話確認済み(デモ表示)。",
        ),
        dict(
            transaction_id="TXN-099300", risk_score=0.45, recommended_action="承認", priority="低",
            status="完了", amount=12000, transaction_datetime=_recent_at(12, 0, days_ago=5),
            merchant="カフェ&ベーカリーSORA", customer_id="CUST-9012", card_last4="8843",
            region="神奈川", channel="モバイル決済", related_transaction_count=1,
            detection_summary="平均よりやや高い金額ですが、通常の利用パターンの範囲内です。",
            risk_factors=[
                _rf("過去平均を上回る金額", "¥12,000", "平均 ¥3,400", "中", "直近の平均取引額をやや上回っています。"),
                _rf("初回利用の加盟店", "初回利用", "利用実績のある加盟店", "低", "これまで利用履歴のない加盟店です。"),
                _rf("通常と異なる深夜帯", "12:00", "08:00〜22:00", "低", "通常利用時間帯に収まっています。"),
            ],
            behavior_comparison=[BehaviorComparisonRow(item="取引金額", current_value="¥12,000", normal_value="平均 ¥3,400")],
            timeline=[_tl(_recent_at(12, 0, days_ago=5), "カフェ&ベーカリーSORA", 12000, "神奈川", "登録済み端末", "正常", "承認")],
            last_7_days_summary=Last7DaysSummary(transaction_count=20, total_amount=41000, average_amount=2050, fraud_flagged_count=0),
            related_info=RelatedInfo(
                related_cards=["末尾8843(今回利用)"], related_devices=["端末ID:AND-9931(登録済み)"],
                related_accounts=["CUST-9012(本人)"], related_merchants=["カフェ&ベーカリーSORA"],
            ),
            rule_reasons=["平均利用額超過ルールに該当(軽微)"],
            ai_top_factors=[_ai("金額逸脱度", 0.14, "直近の平均利用額をやや上回っています。")],
            decision_offset_minutes=40,
            audit_log_extra=[("調査担当者", "調査結果「正常」を登録")],
            investigation_result="正常",
            investigation_memo="通常の飲食利用と判断。",
        ),
        dict(
            transaction_id="TXN-099200", risk_score=0.30, recommended_action="承認", priority="低",
            status="未着手", amount=8600, transaction_datetime=_recent_at(18, 15, days_ago=1),
            merchant="スーパーマーケットまごころ", customer_id="CUST-3305", card_last4="5501",
            region="千葉", channel="デビットカード", related_transaction_count=1,
            detection_summary="通常の生活圏内での低リスクな取引です。",
            risk_factors=[
                _rf("初回利用の加盟店", "初回利用", "利用実績のある加盟店", "低", "これまで利用履歴のない加盟店です。"),
                _rf("過去平均を上回る金額", "¥8,600", "平均 ¥6,800", "低", "平均利用額に近い水準です。"),
                _rf("通常と異なる深夜帯", "18:15", "09:00〜21:00", "低", "通常利用時間帯に収まっています。"),
            ],
            behavior_comparison=[BehaviorComparisonRow(item="取引金額", current_value="¥8,600", normal_value="平均 ¥6,800")],
            timeline=[_tl(_recent_at(18, 15, days_ago=1), "スーパーマーケットまごころ", 8600, "千葉", "登録済み端末", "正常", "承認")],
            last_7_days_summary=Last7DaysSummary(transaction_count=22, total_amount=142000, average_amount=6454, fraud_flagged_count=0),
            related_info=RelatedInfo(
                related_cards=["末尾5501(今回利用)"], related_devices=["端末ID:IOS-1145(登録済み)"],
                related_accounts=["CUST-3305(本人)"], related_merchants=["スーパーマーケットまごころ"],
            ),
            rule_reasons=["該当ルールなし(参考表示)"],
            ai_top_factors=[_ai("金額逸脱度", 0.08, "平均利用額に近い水準です。")],
            decision_offset_minutes=None,
            audit_log_extra=[],
        ),
        dict(
            transaction_id="TXN-099100", risk_score=0.63, recommended_action="保留", priority="中",
            status="完了", amount=54000, transaction_datetime=_recent_at(22, 50, days_ago=6),
            merchant="旅行代理店トラベルウィング", customer_id="CUST-6621", card_last4="7734",
            region="京都", channel="モバイル決済", related_transaction_count=2,
            detection_summary="高額なオンライン旅行予約で、詳細確認が妥当と判断されたケースです。",
            risk_factors=[
                _rf("過去平均を上回る金額", "¥54,000", "平均 ¥8,900", "中", "直近の平均取引額を上回っています。"),
                _rf("初回利用の加盟店", "初回利用", "利用実績のある加盟店", "中", "これまで利用履歴のない加盟店です。"),
                _rf("通常と異なる深夜帯", "22:50", "09:00〜22:00", "低", "やや通常利用時間帯から外れています。"),
            ],
            behavior_comparison=[BehaviorComparisonRow(item="取引金額", current_value="¥54,000", normal_value="平均 ¥8,900")],
            timeline=[
                _tl(_recent_at(22, 50, days_ago=6) - timedelta(minutes=5), "旅行代理店トラベルウィング", 21000, "京都", "登録済み端末", "要確認", "保留"),
                _tl(_recent_at(22, 50, days_ago=6), "旅行代理店トラベルウィング", 54000, "京都", "登録済み端末", "要確認", "保留"),
            ],
            last_7_days_summary=Last7DaysSummary(transaction_count=8, total_amount=36500, average_amount=4563, fraud_flagged_count=0),
            related_info=RelatedInfo(
                related_cards=["末尾7734(今回利用)"], related_devices=["端末ID:AND-5567(登録済み)"],
                related_accounts=["CUST-6621(本人)"], related_merchants=["旅行代理店トラベルウィング"],
            ),
            rule_reasons=["初回加盟店での高額取引ルールに該当"],
            ai_top_factors=[_ai("金額逸脱度", 0.20, "直近の平均利用額を上回っています。"), _ai("加盟店信頼スコア", 0.15, "初回利用の加盟店です。")],
            decision_offset_minutes=210,
            audit_log_extra=[("調査担当者", "調査結果「追加確認」を登録")],
            investigation_result="追加確認",
            investigation_memo="本人へ利用意思を確認中(デモ表示、結果未確定)。",
        ),
        dict(
            transaction_id="TXN-099050", risk_score=0.20, recommended_action="承認", priority="低",
            status="完了", amount=5400, transaction_datetime=_recent_at(11, 30, days_ago=2),
            merchant="ドラッグストアさくら", customer_id="CUST-4489", card_last4="3320",
            region="埼玉", channel="デビットカード", related_transaction_count=1,
            detection_summary="通常利用の範囲内の少額取引です。",
            risk_factors=[
                _rf("初回利用の加盟店", "初回利用", "利用実績のある加盟店", "低", "これまで利用履歴のない加盟店です。"),
                _rf("過去平均を上回る金額", "¥5,400", "平均 ¥4,900", "低", "平均利用額に近い水準です。"),
                _rf("通常と異なる深夜帯", "11:30", "08:00〜22:00", "低", "通常利用時間帯に収まっています。"),
            ],
            behavior_comparison=[BehaviorComparisonRow(item="取引金額", current_value="¥5,400", normal_value="平均 ¥4,900")],
            timeline=[_tl(_recent_at(11, 30, days_ago=2), "ドラッグストアさくら", 5400, "埼玉", "登録済み端末", "正常", "承認")],
            last_7_days_summary=Last7DaysSummary(transaction_count=25, total_amount=118000, average_amount=4720, fraud_flagged_count=0),
            related_info=RelatedInfo(
                related_cards=["末尾3320(今回利用)"], related_devices=["端末ID:IOS-7788(登録済み)"],
                related_accounts=["CUST-4489(本人)"], related_merchants=["ドラッグストアさくら"],
            ),
            rule_reasons=["該当ルールなし(参考表示)"],
            ai_top_factors=[_ai("金額逸脱度", 0.06, "平均利用額に近い水準です。")],
            decision_offset_minutes=15,
            audit_log_extra=[("調査担当者", "調査結果「正常」を登録")],
            investigation_result="正常",
            investigation_memo="通常の日用品購入と判断。",
        ),
    ]
    return cases


def _initial_audit_log(case: dict) -> List[AuditLogEntry]:
    tx_time: datetime = case["transaction_datetime"]
    log = [
        _audit(tx_time + timedelta(minutes=1), "ルールエンジン(自動)", "既存ルールとの照合を実施"),
        _audit(tx_time + timedelta(minutes=1), "AIスコアリング(自動)", f"リスクスコア{case['risk_score']:.2f}を算出"),
        _audit(tx_time + timedelta(minutes=2), "システム", f"優先度「{case['priority']}」で調査キューへ追加"),
    ]
    for actor, action in case.get("audit_log_extra", []):
        offset = case.get("decision_offset_minutes") or 30
        log.append(_audit(tx_time + timedelta(minutes=offset), actor, action))
    return log


_CASES: List[dict] = _build_case_seed()
for _c in _CASES:
    _c["audit_log"] = _initial_audit_log(_c)
    _c.setdefault("investigation_result", None)
    _c.setdefault("investigation_memo", None)
    _c["decision_datetime"] = (
        _c["transaction_datetime"] + timedelta(minutes=_c["decision_offset_minutes"])
        if _c.get("decision_offset_minutes") is not None
        else _c["transaction_datetime"] + timedelta(minutes=3)
    )


def _runtime_cases() -> List[dict]:
    return _CASES


def _case_summary(c: dict) -> CaseSummary:
    return CaseSummary(
        transaction_id=c["transaction_id"], risk_score=c["risk_score"], recommended_action=c["recommended_action"],
        amount=c["amount"], transaction_datetime=_fmt(c["transaction_datetime"]), merchant=c["merchant"],
        detection_summary=c["detection_summary"], related_transaction_count=c["related_transaction_count"],
        priority=c["priority"], status=c["status"], channel=c["channel"], investigation_result=c["investigation_result"],
    )


def _score_band(score: float) -> str:
    if score >= 0.67:
        return "高"
    if score >= 0.34:
        return "中"
    return "低"


def get_case_list(
    status: Optional[Status] = None,
    priority: Optional[Priority] = None,
    recommended_action: Optional[str] = None,
    risk_band: Optional[str] = None,
    query: Optional[str] = None,
) -> CaseListResponse:
    items = _sorted_cases_for_dashboard(_runtime_cases())
    if status is not None:
        items = [c for c in items if c["status"] == status]
    if priority is not None:
        items = [c for c in items if c["priority"] == priority]
    if recommended_action is not None:
        items = [c for c in items if c["recommended_action"] == recommended_action]
    if risk_band is not None:
        items = [c for c in items if _score_band(c["risk_score"]) == risk_band]
    if query:
        q = query.strip().lower()
        items = [c for c in items if q in c["transaction_id"].lower() or q in c["merchant"].lower()]
    summaries = [_case_summary(c) for c in items]
    return CaseListResponse(items=summaries, total=len(summaries))


def _find_case(transaction_id: str) -> Optional[dict]:
    for c in _runtime_cases():
        if c["transaction_id"] == transaction_id:
            return c
    return None


def get_case_detail(transaction_id: str) -> Optional[CaseDetail]:
    c = _find_case(transaction_id)
    if c is None:
        return None
    return CaseDetail(
        transaction_id=c["transaction_id"], risk_score=c["risk_score"], recommended_action=c["recommended_action"],
        priority=c["priority"], status=c["status"], amount=c["amount"],
        transaction_datetime=_fmt(c["transaction_datetime"]), merchant=c["merchant"], customer_id=c["customer_id"],
        card_last4=c["card_last4"], region=c["region"], channel=c["channel"],
        related_transaction_count=c["related_transaction_count"], risk_factors=c["risk_factors"],
        behavior_comparison=c["behavior_comparison"], timeline=c["timeline"],
        last_7_days_summary=c["last_7_days_summary"], related_info=c["related_info"],
        rule_reasons=c["rule_reasons"], ai_top_factors=c["ai_top_factors"], model_version=MODEL_VERSION,
        decision_datetime=_fmt(c["decision_datetime"]), data_updated_at=_fmt(_now()), audit_log=c["audit_log"],
        investigation_result=c["investigation_result"], investigation_memo=c["investigation_memo"],
    )


def apply_decision(transaction_id: str, result: InvestigationResult, memo: Optional[str]) -> Optional[dict]:
    c = _find_case(transaction_id)
    if c is None:
        return None
    c["investigation_result"] = result
    c["investigation_memo"] = memo
    c["status"] = "完了"
    now = _now()
    c["audit_log"].append(_audit(now, "調査担当者", f"調査結果「{result}」を登録"))
    return {
        "transaction_id": c["transaction_id"],
        "investigation_result": result,
        "status": c["status"],
        "memo": memo,
        "updated_at": _fmt(now),
    }

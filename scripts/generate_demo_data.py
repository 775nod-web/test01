"""固定シードで再現可能な合成データ生成スクリプト（Layer 1 / DEMO_SPEC準拠）。

生成するファイル（すべて data/ 配下）:
- customers.csv            顧客マスター（匿名ID・匿名表示名）
- ec_transactions.csv      ECサイト購入履歴（必須データソース）
- payment_transactions.csv QR決済・クレジットカード決済履歴（必須データソース）
- bank_transactions.csv    ネット銀行取引履歴（任意データソース）
- campaigns.csv            過去のマーケティング施策配信と反応（任意データソース）
- customer_support.json    問い合わせ履歴（任意データソース）
- generation_meta.json     生成条件（シード・基準日・期間バケット定義）

このスクリプトは生の取引明細のみを出力する。月次集計・最終利用日・利用サービス数などの
派生特徴量はすべて scripts/prepare_customer360.py が生データから再計算する
（生成時点でのみ存在する内部状態を派生値として重複保持しないことで、
「最終利用日と利用履歴が矛盾しない」というデータ品質要件を構造的に満たす）。

実行方法:
    python scripts/generate_demo_data.py
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

SEED = 42
CUSTOMER_COUNT = 60

# 基準日（このスクリプトの生成結果はこの日付を基準に一貫して再現される）
AS_OF_DATE = date(2026, 7, 16)

# 直近4期間（各30日）の行動推移を追跡する
PERIOD_BUCKETS = 4
BUCKET_LENGTH_DAYS = 30

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

# 60人中 高15人 / 中20人 / 低25人 という常識的なリスク分布にする
RISK_COUNTS = {"high": 15, "medium": 20, "low": 25}

CAMPAIGN_TYPES = [
    "EC再訪促進メール",
    "QR決済ポイント還元",
    "カード利用特典案内",
    "複数サービス横断ポイント施策",
]
CAMPAIGN_RESPONSES = ["反応あり", "開封のみ", "反応なし"]
SUPPORT_CATEGORIES = [
    "利用方法の問い合わせ",
    "決済エラーの相談",
    "退会・解約に関する相談",
    "キャンペーン内容の確認",
]


def bucket_window(bucket_index: int) -> tuple[date, date]:
    """bucket_index=0が最も古く、PERIOD_BUCKETS-1が直近の期間を返す。"""
    end_offset_days = (PERIOD_BUCKETS - 1 - bucket_index) * BUCKET_LENGTH_DAYS
    bucket_end = AS_OF_DATE - timedelta(days=end_offset_days)
    bucket_start = bucket_end - timedelta(days=BUCKET_LENGTH_DAYS - 1)
    return bucket_start, bucket_end


def build_risk_assignment(rng: random.Random) -> list[str]:
    assignment: list[str] = []
    for profile, count in RISK_COUNTS.items():
        assignment.extend([profile] * count)
    rng.shuffle(assignment)
    return assignment


def monthly_multipliers(rng: random.Random, risk: str) -> list[float]:
    """期間ごとの金額倍率（先頭=1.0）。高リスクほど緩やかに低下させる。"""
    multipliers = [1.0]
    if risk == "high":
        for _ in range(PERIOD_BUCKETS - 1):
            drop = rng.uniform(0.22, 0.32)
            multipliers.append(round(multipliers[-1] * (1 - drop), 4))
    elif risk == "medium":
        for _ in range(PERIOD_BUCKETS - 1):
            drop = rng.uniform(0.09, 0.16)
            multipliers.append(round(multipliers[-1] * (1 - drop), 4))
    else:
        for _ in range(PERIOD_BUCKETS - 1):
            change = rng.uniform(-0.03, 0.12)
            multipliers.append(round(multipliers[-1] * (1 + change), 4))
    return multipliers


@dataclass
class ServicePlan:
    subscribed: bool
    base_amount: float
    unit_price: float
    multipliers: list[float]
    discontinue_last_bucket: bool = False


@dataclass
class CustomerPlan:
    customer_id: str
    display_name: str
    signup_date: date
    risk: str
    services: dict[str, ServicePlan] = field(default_factory=dict)


def build_customer_plans(rng: random.Random) -> list[CustomerPlan]:
    risk_assignment = build_risk_assignment(rng)
    plans: list[CustomerPlan] = []

    for i in range(1, CUSTOMER_COUNT + 1):
        customer_id = f"C{i:03d}"
        display_name = f"顧客 {i:03d}"
        risk = risk_assignment[i - 1]

        signup_days_ago = rng.randint(200, 1500)
        signup_date = AS_OF_DATE - timedelta(days=signup_days_ago)

        # サービス利用有無にはばらつきを持たせる。ECは必須ソースなので全員が利用する。
        has_qr = rng.random() < 0.75
        has_card = rng.random() < 0.70
        has_bank = rng.random() < 0.55

        # 高リスク顧客は「複数サービスでの緩やかな低下」を示すため、
        # 決済系サービスのうち最低2つは利用している状態にする。
        if risk == "high":
            payment_flags = [has_qr, has_card, has_bank]
            if sum(payment_flags) < 2:
                has_qr, has_card, has_bank = True, True, has_bank

        services: dict[str, ServicePlan] = {}

        ec_multipliers = monthly_multipliers(rng, risk)
        services["ec"] = ServicePlan(
            subscribed=True,
            base_amount=rng.uniform(30000, 60000),
            unit_price=rng.uniform(3000, 8000),
            multipliers=ec_multipliers,
        )

        non_ec_candidates: list[str] = []
        if has_qr:
            non_ec_candidates.append("qr")
        if has_card:
            non_ec_candidates.append("card")
        if has_bank:
            non_ec_candidates.append("bank")

        # 高リスク顧客は、非ECサービスのうち1つを直近期間で完全停止させ、
        # 「利用サービス数の減少」を再現する。停止対象は基準額が最も小さいものを優先する。
        discontinue_target: str | None = None
        if risk == "high" and non_ec_candidates:
            discontinue_target = min(
                non_ec_candidates,
                key=lambda name: {"qr": 0, "bank": 1, "card": 2}[name],
            )

        if has_qr:
            services["qr"] = ServicePlan(
                subscribed=True,
                base_amount=rng.uniform(25000, 45000),
                unit_price=rng.uniform(800, 3000),
                multipliers=monthly_multipliers(rng, risk),
                discontinue_last_bucket=(discontinue_target == "qr"),
            )
        if has_card:
            services["card"] = ServicePlan(
                subscribed=True,
                base_amount=rng.uniform(35000, 55000),
                unit_price=rng.uniform(2000, 6000),
                multipliers=monthly_multipliers(rng, risk),
                discontinue_last_bucket=(discontinue_target == "card"),
            )
        if has_bank:
            services["bank"] = ServicePlan(
                subscribed=True,
                base_amount=rng.uniform(20000, 80000),
                unit_price=rng.uniform(5000, 20000),
                multipliers=monthly_multipliers(rng, risk),
                discontinue_last_bucket=(discontinue_target == "bank"),
            )

        plans.append(
            CustomerPlan(
                customer_id=customer_id,
                display_name=display_name,
                signup_date=signup_date,
                risk=risk,
                services=services,
            )
        )

    return plans


def split_amount_into_transactions(
    rng: random.Random, total_amount: float, count: int
) -> list[int]:
    """total_amountをcount件のプラスの整数（10円単位）に分割する。"""
    if count <= 0 or total_amount <= 0:
        return []
    weights = [rng.uniform(0.4, 1.6) for _ in range(count)]
    weight_sum = sum(weights)
    raw_amounts = [total_amount * w / weight_sum for w in weights]
    amounts = [max(100, round(a / 10) * 10) for a in raw_amounts]

    # 丸め誤差を最後の要素で補正する（正の値を維持する）
    diff = round(total_amount) - sum(amounts)
    amounts[-1] = max(100, amounts[-1] + diff)
    return [int(a) for a in amounts]


def random_date_in_window(rng: random.Random, start: date, end: date) -> date:
    span = (end - start).days
    return start + timedelta(days=rng.randint(0, span))


def generate_transactions_for_service(
    rng: random.Random,
    customer_id: str,
    plan: ServicePlan,
    id_prefix: str,
) -> list[dict]:
    rows: list[dict] = []
    for bucket_index in range(PERIOD_BUCKETS):
        is_last_bucket = bucket_index == PERIOD_BUCKETS - 1
        if plan.discontinue_last_bucket and is_last_bucket:
            continue  # このサービスは直近期間で完全に利用停止している

        multiplier = plan.multipliers[bucket_index]
        month_amount = plan.base_amount * multiplier
        frequency = max(1, round(month_amount / plan.unit_price))
        amounts = split_amount_into_transactions(rng, month_amount, frequency)

        bucket_start, bucket_end = bucket_window(bucket_index)
        for seq, amount in enumerate(amounts):
            txn_date = random_date_in_window(rng, bucket_start, bucket_end)
            rows.append(
                {
                    "transaction_id": f"{id_prefix}-{customer_id}-{bucket_index}-{seq:02d}",
                    "customer_id": customer_id,
                    "transaction_date": txn_date.isoformat(),
                    "amount": amount,
                }
            )
    return rows


def write_customers_csv(plans: list[CustomerPlan]) -> None:
    path = DATA_DIR / "customers.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["customer_id", "display_name", "signup_date"])
        for plan in plans:
            writer.writerow([plan.customer_id, plan.display_name, plan.signup_date.isoformat()])


def write_ec_transactions(plans: list[CustomerPlan], rng: random.Random) -> None:
    path = DATA_DIR / "ec_transactions.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["order_id", "customer_id", "order_date", "amount"])
        for plan in plans:
            rows = generate_transactions_for_service(rng, plan.customer_id, plan.services["ec"], "ORD")
            rows.sort(key=lambda r: r["transaction_date"])
            for row in rows:
                writer.writerow([row["transaction_id"], row["customer_id"], row["transaction_date"], row["amount"]])


def write_payment_transactions(plans: list[CustomerPlan], rng: random.Random) -> None:
    path = DATA_DIR / "payment_transactions.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["transaction_id", "customer_id", "transaction_date", "payment_method", "amount"])
        all_rows: list[tuple] = []
        for plan in plans:
            if "qr" in plan.services:
                for row in generate_transactions_for_service(rng, plan.customer_id, plan.services["qr"], "QR"):
                    all_rows.append((row["transaction_id"], row["customer_id"], row["transaction_date"], "QR決済", row["amount"]))
            if "card" in plan.services:
                for row in generate_transactions_for_service(rng, plan.customer_id, plan.services["card"], "CARD"):
                    all_rows.append((row["transaction_id"], row["customer_id"], row["transaction_date"], "クレジットカード", row["amount"]))
        all_rows.sort(key=lambda r: (r[1], r[2]))
        for row in all_rows:
            writer.writerow(row)


def write_bank_transactions(plans: list[CustomerPlan], rng: random.Random) -> None:
    path = DATA_DIR / "bank_transactions.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["transaction_id", "customer_id", "transaction_date", "transaction_type", "amount"])
        all_rows: list[tuple] = []
        for plan in plans:
            if "bank" not in plan.services:
                continue
            for row in generate_transactions_for_service(rng, plan.customer_id, plan.services["bank"], "BANK"):
                transaction_type = "入金" if rng.random() < 0.5 else "出金"
                all_rows.append((row["transaction_id"], row["customer_id"], row["transaction_date"], transaction_type, row["amount"]))
        all_rows.sort(key=lambda r: (r[1], r[2]))
        for row in all_rows:
            writer.writerow(row)


def write_campaigns(plans: list[CustomerPlan], rng: random.Random) -> None:
    path = DATA_DIR / "campaigns.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["campaign_id", "customer_id", "sent_date", "campaign_type", "response", "cost"])
        seq = 0
        for plan in plans:
            # 全員が反応済み、または全員が無反応にならないよう、0〜3件を確率的に配信する。
            campaign_count = rng.choices([0, 1, 2, 3], weights=[15, 35, 35, 15])[0]
            for _ in range(campaign_count):
                seq += 1
                sent_days_ago = rng.randint(15, 150)
                sent_date = AS_OF_DATE - timedelta(days=sent_days_ago)
                campaign_type = rng.choice(CAMPAIGN_TYPES)
                response = rng.choices(
                    CAMPAIGN_RESPONSES, weights=[40, 30, 30]
                )[0]
                cost = rng.choice([0, 100, 200, 300, 500])
                writer.writerow(
                    [f"CMP{seq:04d}", plan.customer_id, sent_date.isoformat(), campaign_type, response, cost]
                )


def write_customer_support(plans: list[CustomerPlan], rng: random.Random) -> None:
    path = DATA_DIR / "customer_support.json"
    records = []
    seq = 0
    for plan in plans:
        inquiry_count = rng.choices([0, 1, 2], weights=[55, 30, 15])[0]
        for _ in range(inquiry_count):
            seq += 1
            inquiry_days_ago = rng.randint(5, 200)
            inquiry_date = AS_OF_DATE - timedelta(days=inquiry_days_ago)
            category = rng.choice(SUPPORT_CATEGORIES)
            records.append(
                {
                    "inquiry_id": f"SUP{seq:04d}",
                    "customer_id": plan.customer_id,
                    "inquiry_date": inquiry_date.isoformat(),
                    "category": category,
                    "summary": f"{category}について問い合わせ",
                }
            )
    records.sort(key=lambda r: (r["customer_id"], r["inquiry_date"]))
    with path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_generation_meta() -> None:
    path = DATA_DIR / "generation_meta.json"
    meta = {
        "seed": SEED,
        "as_of_date": AS_OF_DATE.isoformat(),
        "customer_count": CUSTOMER_COUNT,
        "period_buckets": PERIOD_BUCKETS,
        "bucket_length_days": BUCKET_LENGTH_DAYS,
        "risk_counts": RISK_COUNTS,
        "data_sources": [
            "ec_transactions.csv",
            "payment_transactions.csv",
            "bank_transactions.csv",
            "campaigns.csv",
            "customer_support.json",
        ],
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    plans = build_customer_plans(rng)

    write_customers_csv(plans)
    write_ec_transactions(plans, rng)
    write_payment_transactions(plans, rng)
    write_bank_transactions(plans, rng)
    write_campaigns(plans, rng)
    write_customer_support(plans, rng)
    write_generation_meta()

    print(f"合成データを生成しました: {DATA_DIR}")
    print(f"  顧客数: {CUSTOMER_COUNT} (高{RISK_COUNTS['high']} / 中{RISK_COUNTS['medium']} / 低{RISK_COUNTS['low']})")
    print(f"  基準日: {AS_OF_DATE.isoformat()}")


if __name__ == "__main__":
    main()

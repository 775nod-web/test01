"""生データ（data/配下）から顧客360統合ビューを構築するスクリプト（Layer 1）。

customer_idをキーに、EC・QR決済・カード・銀行の各取引明細を月次集計し、
過去施策・問い合わせ履歴とあわせて1顧客1レコードへ統合する。
構造的なデータ品質チェック（負値、全期間ゼロ、重複ID、未来日付など）もここで実行し、
違反があれば処理を失敗させる（不正なデータを artifacts/ へ出力しない）。

実行方法:
    python scripts/prepare_customer360.py

前提:
    scripts/generate_demo_data.py を先に実行し、data/ 配下のファイルが存在すること。
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"

SERVICE_LABELS = {
    "ec": "ECサイト",
    "qr": "QR決済",
    "card": "クレジットカード",
    "bank": "ネット銀行",
}


def load_generation_meta() -> dict:
    with (DATA_DIR / "generation_meta.json").open(encoding="utf-8") as f:
        return json.load(f)


def bucket_index_for_date(
    transaction_date: date, as_of_date: date, period_buckets: int, bucket_length_days: int
) -> Optional[int]:
    days_ago = (as_of_date - transaction_date).days
    total_span = period_buckets * bucket_length_days
    if days_ago < 0 or days_ago >= total_span:
        return None
    bucket_from_end = days_ago // bucket_length_days
    return period_buckets - 1 - bucket_from_end


def safe_pct_change(curr: float, prev: float) -> Optional[float]:
    if prev <= 0:
        return None
    return round((curr - prev) / prev * 100, 1)


class ServiceAggregate:
    def __init__(self, period_buckets: int) -> None:
        self.monthly_amount = [0.0] * period_buckets
        self.monthly_frequency = [0] * period_buckets
        self.last_used_date: Optional[date] = None

    def add(self, bucket_index: int, amount: float, txn_date: date) -> None:
        self.monthly_amount[bucket_index] += amount
        self.monthly_frequency[bucket_index] += 1
        if self.last_used_date is None or txn_date > self.last_used_date:
            self.last_used_date = txn_date

    def to_dict(self, as_of_date: date) -> dict:
        rounded_amount = [round(a) for a in self.monthly_amount]
        days_since_last_used = (
            (as_of_date - self.last_used_date).days if self.last_used_date else None
        )
        return {
            "monthly_amount": rounded_amount,
            "monthly_frequency": self.monthly_frequency,
            "last_used_date": self.last_used_date.isoformat() if self.last_used_date else None,
            "days_since_last_used": days_since_last_used,
            "period_change_pct": safe_pct_change(rounded_amount[-1], rounded_amount[-2])
            if len(rounded_amount) >= 2
            else None,
        }


def read_customers() -> list[dict]:
    path = DATA_DIR / "customers.csv"
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    meta = load_generation_meta()
    as_of_date = parse_date(meta["as_of_date"])
    period_buckets = meta["period_buckets"]
    bucket_length_days = meta["bucket_length_days"]

    violations: list[str] = []

    customer_rows = read_customers()
    customer_ids_seen: dict[str, int] = defaultdict(int)
    for row in customer_rows:
        customer_ids_seen[row["customer_id"]] += 1
    duplicate_ids = [cid for cid, count in customer_ids_seen.items() if count > 1]
    if duplicate_ids:
        violations.append(f"customers.csvにcustomer_idの重複があります: {duplicate_ids}")

    aggregates: dict[str, dict[str, ServiceAggregate]] = {
        row["customer_id"]: {} for row in customer_rows
    }
    negative_amount_found = False
    future_dated_count = 0

    def process_transactions(filename: str, service_key: Optional[str], service_field: Optional[str]) -> None:
        nonlocal negative_amount_found, future_dated_count
        path = DATA_DIR / filename
        if not path.exists():
            return
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                customer_id = row["customer_id"]
                if customer_id not in aggregates:
                    continue
                amount = float(row["amount"])
                if amount < 0:
                    negative_amount_found = True
                txn_date = parse_date(row["transaction_date"] if "transaction_date" in row else row["order_date"])
                if txn_date > as_of_date:
                    future_dated_count += 1
                    continue
                key = service_key if service_key else row[service_field]
                bucket_index = bucket_index_for_date(txn_date, as_of_date, period_buckets, bucket_length_days)
                if bucket_index is None:
                    continue
                service_map = aggregates[customer_id]
                if key not in service_map:
                    service_map[key] = ServiceAggregate(period_buckets)
                service_map[key].add(bucket_index, amount, txn_date)

    process_transactions("ec_transactions.csv", "ec", None)

    # payment_transactions.csv は payment_method 列で qr / card を判定する
    payment_path = DATA_DIR / "payment_transactions.csv"
    if payment_path.exists():
        with payment_path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                customer_id = row["customer_id"]
                if customer_id not in aggregates:
                    continue
                amount = float(row["amount"])
                if amount < 0:
                    negative_amount_found = True
                txn_date = parse_date(row["transaction_date"])
                if txn_date > as_of_date:
                    future_dated_count += 1
                    continue
                key = "qr" if row["payment_method"] == "QR決済" else "card"
                bucket_index = bucket_index_for_date(txn_date, as_of_date, period_buckets, bucket_length_days)
                if bucket_index is None:
                    continue
                service_map = aggregates[customer_id]
                if key not in service_map:
                    service_map[key] = ServiceAggregate(period_buckets)
                service_map[key].add(bucket_index, amount, txn_date)

    process_transactions("bank_transactions.csv", "bank", None)

    # 過去施策
    campaigns_by_customer: dict[str, list[dict]] = defaultdict(list)
    campaigns_path = DATA_DIR / "campaigns.csv"
    if campaigns_path.exists():
        with campaigns_path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                campaigns_by_customer[row["customer_id"]].append(
                    {
                        "sent_date": row["sent_date"],
                        "campaign_type": row["campaign_type"],
                        "response": row["response"],
                        "cost": int(row["cost"]),
                    }
                )
    for records in campaigns_by_customer.values():
        records.sort(key=lambda r: r["sent_date"], reverse=True)

    # 問い合わせ履歴
    support_by_customer: dict[str, list[dict]] = defaultdict(list)
    support_path = DATA_DIR / "customer_support.json"
    if support_path.exists():
        with support_path.open(encoding="utf-8") as f:
            for record in json.load(f):
                support_by_customer[record["customer_id"]].append(record)
    for records in support_by_customer.values():
        records.sort(key=lambda r: r["inquiry_date"], reverse=True)

    customers_output = []
    all_zero_customers: list[str] = []

    for row in customer_rows:
        customer_id = row["customer_id"]
        service_map = aggregates[customer_id]

        services_dict = {}
        total_activity = 0.0
        for key in ("ec", "qr", "card", "bank"):
            if key in service_map:
                service_dict = service_map[key].to_dict(as_of_date)
                services_dict[key] = service_dict
                total_activity += sum(service_dict["monthly_amount"])

        if total_activity <= 0:
            all_zero_customers.append(customer_id)

        service_count = sum(
            1 for key in ("ec", "qr", "card", "bank") if key in services_dict and services_dict[key]["monthly_amount"][-1] > 0
        )
        previous_service_count = sum(
            1
            for key in ("ec", "qr", "card", "bank")
            if key in services_dict and len(services_dict[key]["monthly_amount"]) >= 2 and services_dict[key]["monthly_amount"][-2] > 0
        )

        qr_amounts = services_dict.get("qr", {}).get("monthly_amount", [0] * period_buckets)
        card_amounts = services_dict.get("card", {}).get("monthly_amount", [0] * period_buckets)
        combined_qr_card_amount = [q + c for q, c in zip(qr_amounts, card_amounts)]
        qr_freq = services_dict.get("qr", {}).get("monthly_frequency", [0] * period_buckets)
        card_freq = services_dict.get("card", {}).get("monthly_frequency", [0] * period_buckets)
        combined_qr_card_frequency = [q + c for q, c in zip(qr_freq, card_freq)]
        qr_last = services_dict.get("qr", {}).get("last_used_date")
        card_last = services_dict.get("card", {}).get("last_used_date")
        combined_last_used_str = max([d for d in (qr_last, card_last) if d], default=None)
        combined_last_used = parse_date(combined_last_used_str) if combined_last_used_str else None

        data_sources = ["ec_transactions"]
        if "qr" in services_dict or "card" in services_dict:
            data_sources.append("payment_transactions")
        if "bank" in services_dict:
            data_sources.append("bank_transactions")
        if campaigns_by_customer.get(customer_id):
            data_sources.append("campaigns")
        if support_by_customer.get(customer_id):
            data_sources.append("customer_support")

        support_records = support_by_customer.get(customer_id, [])

        customers_output.append(
            {
                "customer_id": customer_id,
                "display_name": row["display_name"],
                "signup_date": row["signup_date"],
                "services": services_dict,
                "service_count": service_count,
                "previous_service_count": previous_service_count,
                "combined_qr_card": {
                    "monthly_amount": [round(a) for a in combined_qr_card_amount],
                    "monthly_frequency": combined_qr_card_frequency,
                    "last_used_date": combined_last_used.isoformat() if combined_last_used else None,
                    "days_since_last_used": (as_of_date - combined_last_used).days if combined_last_used else None,
                    "period_change_pct": safe_pct_change(
                        round(combined_qr_card_amount[-1]), round(combined_qr_card_amount[-2])
                    )
                    if len(combined_qr_card_amount) >= 2
                    else None,
                },
                "campaigns": campaigns_by_customer.get(customer_id, []),
                "support_summary": {
                    "inquiry_count": len(support_records),
                    "last_inquiry_date": support_records[0]["inquiry_date"] if support_records else None,
                    "recent_categories": [r["category"] for r in support_records[:2]],
                },
                "data_sources": data_sources,
            }
        )

    if negative_amount_found:
        violations.append("負の取引金額が検出されました。")
    if all_zero_customers:
        violations.append(f"全期間ゼロの顧客が存在します: {all_zero_customers}")
    if future_dated_count > 0:
        violations.append(f"未来日付の取引が{future_dated_count}件検出されました。")

    if violations:
        print("データ品質チェックに失敗しました:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        sys.exit(1)

    amounts_all: list[float] = []
    for customer in customers_output:
        for service in customer["services"].values():
            amounts_all.extend(service["monthly_amount"])

    data_quality = {
        "negative_amount_found": negative_amount_found,
        "all_zero_customer_count": len(all_zero_customers),
        "duplicate_customer_id_count": len(duplicate_ids),
        "future_dated_transaction_count": future_dated_count,
        "amount_min": min(amounts_all) if amounts_all else None,
        "amount_max": max(amounts_all) if amounts_all else None,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": as_of_date.isoformat(),
        "customer_count": len(customers_output),
        "data_sources": meta["data_sources"],
        "customers": customers_output,
        "data_quality": data_quality,
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ARTIFACTS_DIR / "customer360.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"顧客360を生成しました: {output_path}")
    print(f"  顧客数: {len(customers_output)}")
    print(f"  データ品質チェック: 問題なし")


if __name__ == "__main__":
    main()

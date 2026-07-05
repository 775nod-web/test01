"""Gold layerテーブルに対するクエリ定義。

店舗別アクセス制御は、Unity Catalogの行フィルタが利用できない場合の
フォールバックとして、ここでAPI側フィルタ（allowed_stores）を実装する。
行フィルタが有効な環境では allowed_stores=None を渡せばよい
（UC側で自動的に絞り込まれる）。
"""
from .config import fq
from .db import run_query


def get_allowed_stores(user_email: str | None) -> list[str] | None:
    """user_store_mapping からユーザーが閲覧可能な store_id 一覧を取得する。

    - user_email が None（未認証/ローカル動作確認）の場合は None を返し、フィルタなし扱いとする。
    - admins グループ相当の全店舗閲覧権限は、マッピングテーブルに全store_idを
      登録するか、UC行フィルタ側のis_account_group_member('admins')判定に委ねる。
    """
    if not user_email:
        return None
    rows = run_query(
        f"SELECT store_id FROM {fq('user_store_mapping')} WHERE user_email = :user_email",
        {"user_email": user_email},
    )
    if not rows:
        return []
    return [row["store_id"] for row in rows]


def _store_filter_clause(allowed_stores: list[str] | None, store_id: str | None, params: dict) -> str:
    clauses = []
    if store_id:
        clauses.append("store_id = :store_id")
        params["store_id"] = store_id
    if allowed_stores is not None:
        if not allowed_stores:
            # 閲覧可能店舗が0件 = 何も返さない
            clauses.append("1=0")
        else:
            placeholders = ", ".join(f"'{s}'" for s in allowed_stores)
            clauses.append(f"store_id IN ({placeholders})")
    return f"WHERE {' AND '.join(clauses)}" if clauses else ""


def get_kpi_summary(date_from: str, date_to: str, store_id: str | None, allowed_stores: list[str] | None) -> dict:
    params: dict = {"date_from": date_from, "date_to": date_to}
    where = _store_filter_clause(allowed_stores, store_id, params)
    where_sql = (where + " AND sales_date BETWEEN :date_from AND :date_to") if where \
        else "WHERE sales_date BETWEEN :date_from AND :date_to"

    rows = run_query(
        f"""
        SELECT
            SUM(total_sales_amount) AS net_sales,
            SUM(transaction_count)  AS transaction_count,
            SUM(total_quantity)     AS units_sold
        FROM {fq('gold_daily_store_sales')}
        {where_sql}
        """,
        params,
    )
    row = rows[0] if rows else {}
    net_sales = row.get("net_sales") or 0
    transaction_count = row.get("transaction_count") or 0
    units_sold = row.get("units_sold") or 0
    average_basket_size = (net_sales / transaction_count) if transaction_count else 0

    return {
        "net_sales": net_sales,
        # 既知のギャップ: Gold layerにdiscount集約列がないためgross salesを正確に算出できない。
        # net salesと同値の暫定値を返し、フロントエンドで注記表示する。
        "gross_sales": net_sales,
        "gross_sales_is_estimated": True,
        "transaction_count": transaction_count,
        "units_sold": units_sold,
        "average_basket_size": average_basket_size,
    }


def get_daily_store_sales(date_from: str, date_to: str, store_id: str | None, allowed_stores: list[str] | None) -> list[dict]:
    params: dict = {"date_from": date_from, "date_to": date_to}
    where = _store_filter_clause(allowed_stores, store_id, params)
    where_sql = (where + " AND sales_date BETWEEN :date_from AND :date_to") if where \
        else "WHERE sales_date BETWEEN :date_from AND :date_to"

    return run_query(
        f"""
        SELECT sales_date, store_id, store_name, region,
               transaction_count, total_quantity, total_sales_amount
        FROM {fq('gold_daily_store_sales')}
        {where_sql}
        ORDER BY sales_date, store_id
        """,
        params,
    )


def get_category_sales() -> list[dict]:
    return run_query(
        f"""
        SELECT category, product_count, transaction_count, total_quantity, total_sales_amount
        FROM {fq('gold_category_sales')}
        ORDER BY total_sales_amount DESC
        """
    )


def get_store_ranking(limit: int, allowed_stores: list[str] | None) -> list[dict]:
    params: dict = {"limit": limit}
    where = ""
    if allowed_stores is not None:
        if not allowed_stores:
            where = "WHERE 1=0"
        else:
            placeholders = ", ".join(f"'{s}'" for s in allowed_stores)
            where = f"WHERE store_id IN ({placeholders})"

    return run_query(
        f"""
        SELECT sales_rank, store_id, store_name, region, store_type,
               total_sales_amount, total_quantity, transaction_count
        FROM {fq('gold_store_ranking')}
        {where}
        ORDER BY sales_rank
        LIMIT :limit
        """,
        params,
    )


def get_quarantine_report(issue_type: str | None) -> list[dict]:
    params: dict = {}
    where = ""
    if issue_type:
        where = "WHERE issue_type = :issue_type"
        params["issue_type"] = issue_type

    return run_query(
        f"""
        SELECT transaction_id, issue_type, store_id, product_id, customer_id,
               transaction_datetime, is_store_registered, is_product_registered,
               quantity, unit_price, discount_amount, sales_amount
        FROM {fq('gold_unregistered_master_report')}
        {where}
        ORDER BY transaction_datetime DESC
        """,
        params,
    )


def get_quarantine_summary() -> list[dict]:
    """issue_type別の未登録件数サマリー（追加機能・優先度中: 品質ヘルス表示の簡易版）。

    transaction_datetimeを日付に丸めて時系列トレンドを見せる。
    """
    return run_query(
        f"""
        SELECT
            CAST(transaction_datetime AS DATE) AS report_date,
            issue_type,
            COUNT(*) AS unregistered_count
        FROM {fq('gold_unregistered_master_report')}
        GROUP BY CAST(transaction_datetime AS DATE), issue_type
        ORDER BY report_date DESC
        """
    )


def get_alerts() -> list[dict]:
    """gold_sales_alerts テーブル（sql/04_alerts_table.sql, jobs/sales_drop_alert_job.py で作成・更新）を参照する。

    テーブル未作成の場合は空リストを返す。
    """
    try:
        return run_query(
            f"""
            SELECT alert_date, store_id, store_name, sales_change_pct, threshold_pct, message
            FROM {fq('gold_sales_alerts')}
            ORDER BY alert_date DESC, sales_change_pct ASC
            """
        )
    except RuntimeError:
        return []


def log_access(user_email: str | None, endpoint: str, store_id_filter: str | None) -> None:
    """system.access.audit が利用できない場合のフォールバック監査ログ（追加機能）。

    書き込み失敗はAPIレスポンスに影響させないよう握りつぶす。
    """
    try:
        run_query(
            f"""
            INSERT INTO {fq('app_access_log')} (event_time, user_email, endpoint, store_id_filter)
            VALUES (current_timestamp(), :user_email, :endpoint, :store_id_filter)
            """,
            {"user_email": user_email or "unknown", "endpoint": endpoint, "store_id_filter": store_id_filter},
        )
    except RuntimeError:
        pass

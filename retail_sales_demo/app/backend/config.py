import os

# Serverless Starter Warehouse（指定済みID。変更しないこと）
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "50153ad923fecd73")

# Gold layerのカタログ/スキーマ名。実ワークスペースで確認済み: workspace.gold
GOLD_CATALOG = os.environ.get("GOLD_CATALOG", "workspace")
GOLD_SCHEMA = os.environ.get("GOLD_SCHEMA", "gold")

# 売上急減アラートのしきい値（前日比%。デフォルト-20%）
SALES_DROP_ALERT_THRESHOLD_PCT = float(os.environ.get("SALES_DROP_ALERT_THRESHOLD_PCT", "-20"))

# quarantine再照合ジョブのJob ID（Databricks Jobs作成後にAppsの環境変数として設定する）
RECONCILE_JOB_ID = os.environ.get("RECONCILE_JOB_ID")

# Databricks Apps の「ユーザー認可（on-behalf-of-user）」利用時、
# リクエストヘッダでフォワードされる実行ユーザーのメールアドレス。
# 未設定（ローカル動作確認等）の場合はNoneを返しダミーユーザー扱いにする。
FORWARDED_USER_HEADER = "X-Forwarded-Email"


def fq(table: str) -> str:
    """catalog.schema.table 形式の完全修飾テーブル名を返す"""
    return f"{GOLD_CATALOG}.{GOLD_SCHEMA}.{table}"

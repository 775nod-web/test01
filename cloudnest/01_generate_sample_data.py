"""
CloudNest サンプルデータ生成スクリプト（Databricks ノートブック用）
======================================================
B2B SaaS企業「CloudNest」の疑似データを生成する。
実際の3,000社規模を代表するサンプルとして 350社（アクティブ300社＋解約済み50社）を生成し、
以下5つのソースシステムを模擬する。

  1. customer_master   … 顧客マスター（企業名・業界・従業員規模・CSM・地域）
  2. contracts          … 契約データ（プラン・ARR・契約期間・ステータス）
  3. usage_logs         … プロダクト利用ログ（日次集計：ログイン・プロジェクト作成・コメント・ファイル共有・API利用）
  4. support_tickets     … サポートチケット（優先度・ステータス・解決時間・CSAT・本文テキスト）
  5. billing             … 請求データ（支払い状況・プラン変更履歴）

各顧客に「ペルソナ」（Champion / Healthy / Watch / AtRisk）を割り当て、
利用率トレンド・チケット傾向・支払い状況・更新までの日数を相関させることで、
ヘルススコア／解約リスクモデルが意味のあるシグナルを学習・検知できるようにしている。
（ペルソナ自体は実システムには存在しない値のため `_persona_label` として明示し、
 検証・デモ用の答え合わせラベルとして扱う）
"""

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, DateType, BooleanType
)
import random
from datetime import date, timedelta

# Databricks ノートブックでは spark はクラスターから自動注入されるため
# SparkSession.builder は呼ばない（呼ぶと INVALID_CONNECT_URL エラーになる）

random.seed(42)

TODAY = date.today()

# ──────────────────────────────────────────────
# 0. マスターデータ定義
# ──────────────────────────────────────────────

NUM_CUSTOMERS = 350  # 実際の3,000社のうち代表サンプルとして生成（本番PoCではソースシステムから全量連携）

INDUSTRIES = ["SaaS/IT", "製造", "金融", "小売", "医療", "教育", "物流", "建設", "メディア", "コンサルティング"]
REGIONS = ["日本", "北米", "欧州", "APAC"]
EMPLOYEE_BANDS = ["1-50", "51-200", "201-1000", "1001+"]

CSM_OWNERS = [
    "佐藤 麻衣", "鈴木 健太", "高橋 美咲", "田中 大輔", "伊藤 由美",
    "渡辺 翔太", "中村 恵子", "小林 拓海", "加藤 奈々", "吉田 亮",
]

JP_STEMS = ["ノヴァ", "アルテ", "クラウドギア", "フュージョン", "テラス", "ブリッジ", "オリオン",
            "ヴェクター", "ソラリス", "キューブ", "リンクス", "パルテ", "エコシス", "ネクサス", "アビス"]
GLOBAL_STEMS = ["Nova", "Arte", "CloudGear", "Fusion", "Terrace", "Bridge", "Orion",
                "Vector", "Solaris", "Cube", "Lynx", "Parte", "Ecosys", "Nexus", "Abyss"]
GLOBAL_SUFFIXES = ["Inc.", "Corp.", "Solutions", "Technologies", "Group", "Systems"]

# ペルソナ定義：利用率トレンド・チケット傾向・支払い状況・解約確率を左右する
PERSONA_CHAMPION = "CHAMPION"
PERSONA_HEALTHY = "HEALTHY"
PERSONA_WATCH = "WATCH"
PERSONA_AT_RISK = "AT_RISK"

PERSONA_WEIGHTS = {
    PERSONA_CHAMPION: 0.15,
    PERSONA_HEALTHY: 0.40,
    PERSONA_WATCH: 0.25,
    PERSONA_AT_RISK: 0.20,
}

# ペルソナ別：実際に解約に至る確率（履歴データ生成・将来の解約予測モデル学習用ラベルに使用）
CHURN_PROBABILITY = {
    PERSONA_CHAMPION: 0.0,
    PERSONA_HEALTHY: 0.02,
    PERSONA_WATCH: 0.15,
    PERSONA_AT_RISK: 0.65,
}

# ペルソナ別：契約更新までの残日数レンジ（Watch/AtRiskほど更新間近に偏らせ、
# 「更新前に利用率が低下している顧客」を検知できるデータにする）
RENEWAL_DAYS_RANGE = {
    PERSONA_CHAMPION: (120, 365),
    PERSONA_HEALTHY: (60, 365),
    PERSONA_WATCH: (15, 200),
    PERSONA_AT_RISK: (5, 150),
}

# ペルソナ別：エンゲージメント率（seat数に対するDAU比率）と利用トレンド傾き（1日あたり）
ENGAGEMENT_PARAMS = {
    PERSONA_CHAMPION: {"engagement": (0.55, 0.75), "slope": (0.0005, 0.0015)},
    PERSONA_HEALTHY: {"engagement": (0.35, 0.55), "slope": (-0.0005, 0.0005)},
    PERSONA_WATCH: {"engagement": (0.30, 0.45), "slope": (-0.0035, -0.0015)},
    PERSONA_AT_RISK: {"engagement": (0.25, 0.40), "slope": (-0.0080, -0.0040)},
}

# ペルソナ別：月あたり平均チケット数、優先度分布、CSATレンジ、解決時間レンジ
TICKET_PARAMS = {
    PERSONA_CHAMPION: {"rate": 0.3, "priority_w": {"Low": 0.6, "Medium": 0.3, "High": 0.1, "Critical": 0.0}, "csat": (4, 5), "resolution_h": (1, 8)},
    PERSONA_HEALTHY: {"rate": 0.6, "priority_w": {"Low": 0.45, "Medium": 0.35, "High": 0.17, "Critical": 0.03}, "csat": (3, 5), "resolution_h": (2, 24)},
    PERSONA_WATCH: {"rate": 1.2, "priority_w": {"Low": 0.25, "Medium": 0.35, "High": 0.30, "Critical": 0.10}, "csat": (2, 4), "resolution_h": (8, 48)},
    PERSONA_AT_RISK: {"rate": 2.0, "priority_w": {"Low": 0.15, "Medium": 0.30, "High": 0.35, "Critical": 0.20}, "csat": (1, 3), "resolution_h": (24, 96)},
}

# ペルソナ別：請求延滞確率、プラン変更傾向
BILLING_PARAMS = {
    PERSONA_CHAMPION: {"overdue_prob": 0.01, "change": {"Upgrade": 0.15, "None": 0.85}},
    PERSONA_HEALTHY: {"overdue_prob": 0.05, "change": {"Upgrade": 0.05, "None": 0.93, "Downgrade": 0.02}},
    PERSONA_WATCH: {"overdue_prob": 0.18, "change": {"Upgrade": 0.02, "None": 0.83, "Downgrade": 0.15}},
    PERSONA_AT_RISK: {"overdue_prob": 0.35, "change": {"Upgrade": 0.0, "None": 0.70, "Downgrade": 0.30}},
}

BAND_SEATS = {
    "1-50": (5, 40),
    "51-200": (20, 150),
    "201-1000": (80, 500),
    "1001+": (300, 1500),
}

PLANS_BY_BAND = {
    "1-50": [("Starter", (3000, 8000)), ("Standard", (8000, 15000))],
    "51-200": [("Standard", (15000, 40000)), ("Enterprise", (40000, 80000))],
    "201-1000": [("Enterprise", (60000, 150000))],
    "1001+": [("Enterprise", (150000, 400000))],
}

# サポートチケットの本文テンプレート（ペルソナ＝感情トーンごとに分類。NLP分析デモの正解ラベルとして活用）
TICKET_TEMPLATES_NEGATIVE = [
    ("画面の読み込みが遅く、業務に支障が出ています。至急改善してほしいです。", "パフォーマンス"),
    ("サポートの返信が遅すぎて困っています。正直、解約も検討し始めています。", "解約検討"),
    ("エラーが頻発してプロジェクトが作成できません。何度も同じ問題が起きています。", "不具合"),
    ("この料金プランに対して機能が見合っていないと感じています。他社サービスも比較中です。", "料金不満"),
    ("何度も同じ問い合わせをしているのに一向に改善されず、非常に困惑しています。", "対応不満"),
    ("ファイル共有機能がまた落ちました。信頼して使い続けられるか不安です。", "不具合"),
    ("API連携が突然動かなくなり、社内システムに影響が出ています。早急な対応をお願いします。", "不具合"),
]
TICKET_TEMPLATES_NEUTRAL = [
    ("APIキーの発行方法を教えてください。", "利用方法"),
    ("新しいメンバーの追加方法について確認したいです。", "利用方法"),
    ("ファイル共有の権限設定について質問があります。", "利用方法"),
    ("請求書の宛先変更をお願いします。", "請求"),
    ("プロジェクトテンプレートの使い方を知りたいです。", "利用方法"),
    ("パスワードリセットの手順を教えてください。", "利用方法"),
    ("シングルサインオン（SSO）の設定方法について教えてください。", "利用方法"),
]
TICKET_TEMPLATES_POSITIVE = [
    ("新機能について詳しく知りたいので導入相談をしたいです。", "アップセル"),
    ("追加ライセンスの購入を検討しています。見積もりをお願いします。", "アップセル"),
    ("他部署への展開を考えているので活用事例を教えてください。", "アップセル"),
    ("非常に使いやすく助かっています。応用的な使い方を相談したいです。", "活用相談"),
]


def random_date(start: date, end: date) -> date:
    """start〜end の範囲でランダムな日付を返す（start > end の場合は同日を返す）"""
    if start >= end:
        return start
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def weighted_choice(weight_dict):
    """{選択肢: 重み} の辞書から重み付きランダム選択する"""
    keys = list(weight_dict.keys())
    weights = list(weight_dict.values())
    return random.choices(keys, weights=weights, k=1)[0]


def make_company_name(region: str, idx: int) -> str:
    if region == "日本":
        return f"株式会社{random.choice(JP_STEMS)}{idx}"
    stem = random.choice(GLOBAL_STEMS)
    suffix = random.choice(GLOBAL_SUFFIXES)
    return f"{stem} {suffix} {idx}"


# ──────────────────────────────────────────────
# 1. 顧客マスター + 2. 契約データ 生成
#    （同時にペルソナ・解約有無・契約更新日を決定するため一緒に生成する）
# ──────────────────────────────────────────────

customer_rows = []
contract_rows = []
customer_context = {}  # customer_id -> 生成パラメータ（後続の利用ログ/チケット/請求生成で使用）

for i in range(1, NUM_CUSTOMERS + 1):
    customer_id = f"C{str(i).zfill(4)}"
    region = random.choice(REGIONS)
    industry = random.choice(INDUSTRIES)
    employee_band = random.choice(EMPLOYEE_BANDS)
    csm_owner = random.choice(CSM_OWNERS)
    persona = weighted_choice(PERSONA_WEIGHTS)
    company_name = make_company_name(region, i)

    # 解約有無の決定（ペルソナ別確率）
    is_churned = random.random() < CHURN_PROBABILITY[persona]

    # 契約更新までの残日数（解約済みでない顧客のみ意味を持つ）
    renewal_low, renewal_high = RENEWAL_DAYS_RANGE[persona]
    days_to_renewal = random.randint(renewal_low, renewal_high)

    contract_start_date = TODAY + timedelta(days=days_to_renewal) - timedelta(days=365)
    contract_end_date = TODAY + timedelta(days=days_to_renewal)
    churn_date = None
    contract_status = "Active"

    if is_churned:
        # 解約済み：契約終了日を過去日に設定し、解約日として扱う
        churn_date = TODAY - timedelta(days=random.randint(10, 300))
        contract_start_date = churn_date - timedelta(days=365)
        contract_end_date = churn_date
        contract_status = "Cancelled"
    elif days_to_renewal <= 0:
        contract_status = "PendingRenewal"

    signup_date = contract_start_date

    plan_options = PLANS_BY_BAND[employee_band]
    plan_name, arr_range = random.choice(plan_options)
    arr_usd = round(random.uniform(*arr_range), -2)  # 100ドル単位に丸め

    auto_renew = random.random() < (0.7 if persona in (PERSONA_CHAMPION, PERSONA_HEALTHY) else 0.35)

    # 契約ライセンス数（座席数）：CSチームが「利用率＝DAU／ライセンス数」を計算する基準値
    seat_low, seat_high = BAND_SEATS[employee_band]
    seat_count = random.randint(seat_low, seat_high)

    customer_rows.append(Row(
        customer_id=customer_id,
        company_name=company_name,
        industry=industry,
        employee_band=employee_band,
        region=region,
        csm_owner=csm_owner,
        signup_date=signup_date,
        is_churned=is_churned,
        churn_date=churn_date,
        _persona_label=persona,  # デモ・検証用の答え合わせラベル（実システムには存在しない）
    ))

    contract_rows.append(Row(
        contract_id=f"CTR{str(i).zfill(4)}",
        customer_id=customer_id,
        plan=plan_name,
        arr_usd=arr_usd,
        licensed_seats=seat_count,
        contract_start_date=contract_start_date,
        contract_end_date=contract_end_date,
        contract_status=contract_status,
        auto_renew=auto_renew,
    ))

    # 利用ログ・チケット・請求を生成する期間（アクティブ期間の直近180日、または解約日まで）
    window_end = churn_date if is_churned else TODAY
    window_start = max(contract_start_date, window_end - timedelta(days=180))

    customer_context[customer_id] = {
        "persona": persona,
        "seat_count": seat_count,
        "window_start": window_start,
        "window_end": window_end,
        "arr_usd": arr_usd,
    }

customer_schema = StructType([
    StructField("customer_id", StringType(), nullable=False),
    StructField("company_name", StringType(), nullable=True),
    StructField("industry", StringType(), nullable=True),
    StructField("employee_band", StringType(), nullable=True),
    StructField("region", StringType(), nullable=True),
    StructField("csm_owner", StringType(), nullable=True),
    StructField("signup_date", DateType(), nullable=True),
    StructField("is_churned", BooleanType(), nullable=True),
    StructField("churn_date", DateType(), nullable=True),
    StructField("_persona_label", StringType(), nullable=True),
])
df_customer_master = spark.createDataFrame(customer_rows, schema=customer_schema)

contract_schema = StructType([
    StructField("contract_id", StringType(), nullable=False),
    StructField("customer_id", StringType(), nullable=True),
    StructField("plan", StringType(), nullable=True),
    StructField("arr_usd", DoubleType(), nullable=True),
    StructField("licensed_seats", IntegerType(), nullable=True),
    StructField("contract_start_date", DateType(), nullable=True),
    StructField("contract_end_date", DateType(), nullable=True),
    StructField("contract_status", StringType(), nullable=True),
    StructField("auto_renew", BooleanType(), nullable=True),
])
df_contracts = spark.createDataFrame(contract_rows, schema=contract_schema)

print(f"=== 顧客マスター（{df_customer_master.count()}件） ===")
df_customer_master.show(10, truncate=False)
print(f"=== 契約データ（{df_contracts.count()}件） ===")
df_contracts.show(10, truncate=False)


# ──────────────────────────────────────────────
# 3. プロダクト利用ログ（日次集計）生成
# ──────────────────────────────────────────────

usage_rows = []
for customer_id, ctx in customer_context.items():
    persona = ctx["persona"]
    seat_count = ctx["seat_count"]
    window_start = ctx["window_start"]
    window_end = ctx["window_end"]
    window_days = max((window_end - window_start).days, 1)

    eng_low, eng_high = ENGAGEMENT_PARAMS[persona]["engagement"]
    base_engagement = random.uniform(eng_low, eng_high)
    slope_low, slope_high = ENGAGEMENT_PARAMS[persona]["slope"]
    slope = random.uniform(slope_low, slope_high)

    current_date = window_start
    day_offset = 0
    while current_date <= window_end:
        trend_factor = max(1 + slope * day_offset, 0.05)
        noise = random.uniform(0.85, 1.15)
        dau = max(int(seat_count * base_engagement * trend_factor * noise), 0)
        dau = min(dau, seat_count)

        login_count = int(dau * random.uniform(1.2, 3.0))
        project_created_count = int(dau * random.uniform(0.0, 0.3))
        comment_count = int(dau * random.uniform(0.5, 4.0))
        file_shared_count = int(dau * random.uniform(0.2, 1.5))
        api_call_count = int(dau * random.uniform(0, 20)) if persona in (PERSONA_CHAMPION, PERSONA_HEALTHY) else int(dau * random.uniform(0, 4))

        usage_rows.append(Row(
            usage_date=current_date,
            customer_id=customer_id,
            daily_active_users=dau,
            login_count=login_count,
            project_created_count=project_created_count,
            comment_count=comment_count,
            file_shared_count=file_shared_count,
            api_call_count=api_call_count,
        ))

        current_date += timedelta(days=1)
        day_offset += 1

usage_schema = StructType([
    StructField("usage_date", DateType(), nullable=False),
    StructField("customer_id", StringType(), nullable=False),
    StructField("daily_active_users", IntegerType(), nullable=True),
    StructField("login_count", IntegerType(), nullable=True),
    StructField("project_created_count", IntegerType(), nullable=True),
    StructField("comment_count", IntegerType(), nullable=True),
    StructField("file_shared_count", IntegerType(), nullable=True),
    StructField("api_call_count", IntegerType(), nullable=True),
])
df_usage_logs = spark.createDataFrame(usage_rows, schema=usage_schema)

print(f"=== プロダクト利用ログ（{df_usage_logs.count()}件） ===")
df_usage_logs.show(10, truncate=False)


# ──────────────────────────────────────────────
# 4. サポートチケット 生成
# ──────────────────────────────────────────────

ticket_rows = []
ticket_seq = 1
for customer_id, ctx in customer_context.items():
    persona = ctx["persona"]
    window_start = ctx["window_start"]
    window_end = ctx["window_end"]
    window_months = max((window_end - window_start).days / 30, 0.5)

    params = TICKET_PARAMS[persona]
    num_tickets = max(int(round(random.gauss(params["rate"] * window_months, 1.0))), 0)

    for _ in range(num_tickets):
        created_date = random_date(window_start, window_end)
        priority = weighted_choice(params["priority_w"])
        csat_low, csat_high = params["csat"]
        csat_score = random.randint(csat_low, csat_high)
        res_low, res_high = params["resolution_h"]
        resolution_hours = round(random.uniform(res_low, res_high), 1)
        status = random.choices(["Resolved", "Closed", "In Progress", "Open"], weights=[0.55, 0.30, 0.10, 0.05], k=1)[0]

        # 感情トーンをペルソナに応じて重み付け選択（NLP分析の正解データとして機能）
        if persona == PERSONA_AT_RISK:
            template_pool, sentiment_label = random.choices(
                [(TICKET_TEMPLATES_NEGATIVE, "Negative"), (TICKET_TEMPLATES_NEUTRAL, "Neutral")],
                weights=[0.7, 0.3], k=1)[0]
        elif persona == PERSONA_WATCH:
            template_pool, sentiment_label = random.choices(
                [(TICKET_TEMPLATES_NEGATIVE, "Negative"), (TICKET_TEMPLATES_NEUTRAL, "Neutral")],
                weights=[0.4, 0.6], k=1)[0]
        elif persona == PERSONA_CHAMPION:
            template_pool, sentiment_label = random.choices(
                [(TICKET_TEMPLATES_POSITIVE, "Positive"), (TICKET_TEMPLATES_NEUTRAL, "Neutral")],
                weights=[0.5, 0.5], k=1)[0]
        else:
            template_pool, sentiment_label = random.choices(
                [(TICKET_TEMPLATES_NEUTRAL, "Neutral"), (TICKET_TEMPLATES_NEGATIVE, "Negative"), (TICKET_TEMPLATES_POSITIVE, "Positive")],
                weights=[0.7, 0.2, 0.1], k=1)[0]

        description, topic = random.choice(template_pool)

        ticket_rows.append(Row(
            ticket_id=f"TKT{str(ticket_seq).zfill(6)}",
            customer_id=customer_id,
            created_date=created_date,
            priority=priority,
            status=status,
            resolution_hours=resolution_hours if status in ("Resolved", "Closed") else None,
            csat_score=csat_score if status in ("Resolved", "Closed") else None,
            subject=description[:20] + "…",
            description=description,
            _true_sentiment_label=sentiment_label,  # NLP分析結果の答え合わせ用（実システムには存在しない）
            _true_topic_label=topic,
        ))
        ticket_seq += 1

ticket_schema = StructType([
    StructField("ticket_id", StringType(), nullable=False),
    StructField("customer_id", StringType(), nullable=True),
    StructField("created_date", DateType(), nullable=True),
    StructField("priority", StringType(), nullable=True),
    StructField("status", StringType(), nullable=True),
    StructField("resolution_hours", DoubleType(), nullable=True),
    StructField("csat_score", IntegerType(), nullable=True),
    StructField("subject", StringType(), nullable=True),
    StructField("description", StringType(), nullable=True),
    StructField("_true_sentiment_label", StringType(), nullable=True),
    StructField("_true_topic_label", StringType(), nullable=True),
])
df_support_tickets = spark.createDataFrame(ticket_rows, schema=ticket_schema)

print(f"=== サポートチケット（{df_support_tickets.count()}件） ===")
df_support_tickets.show(10, truncate=False)


# ──────────────────────────────────────────────
# 5. 請求データ 生成
# ──────────────────────────────────────────────

billing_rows = []
invoice_seq = 1
for customer_id, ctx in customer_context.items():
    persona = ctx["persona"]
    arr_usd = ctx["arr_usd"]
    window_start = ctx["window_start"]
    window_end = ctx["window_end"]
    params = BILLING_PARAMS[persona]
    monthly_amount = round(arr_usd / 12, 2)

    billing_date = window_start
    while billing_date <= window_end:
        is_overdue = random.random() < params["overdue_prob"]
        payment_status = "Overdue" if is_overdue else random.choices(
            ["Paid", "Failed"], weights=[0.97, 0.03], k=1)[0]
        plan_change_type = weighted_choice(params["change"])

        billing_rows.append(Row(
            invoice_id=f"INV{str(invoice_seq).zfill(6)}",
            customer_id=customer_id,
            billing_date=billing_date,
            amount_usd=monthly_amount,
            payment_status=payment_status,
            plan_change_type=plan_change_type,
        ))
        invoice_seq += 1
        billing_date += timedelta(days=30)

billing_schema = StructType([
    StructField("invoice_id", StringType(), nullable=False),
    StructField("customer_id", StringType(), nullable=True),
    StructField("billing_date", DateType(), nullable=True),
    StructField("amount_usd", DoubleType(), nullable=True),
    StructField("payment_status", StringType(), nullable=True),
    StructField("plan_change_type", StringType(), nullable=True),
])
df_billing = spark.createDataFrame(billing_rows, schema=billing_schema)

print(f"=== 請求データ（{df_billing.count()}件） ===")
df_billing.show(10, truncate=False)


# ──────────────────────────────────────────────
# 6. Spark テンポラリビューとして登録
#    ※ パブリック DBFS ルートが無効な Databricks 環境では
#      /tmp への Parquet 書き込みが禁止されるため、
#      テンポラリビューを使用してセッション内で SQL 参照できるようにする
# ──────────────────────────────────────────────

df_customer_master.createOrReplaceTempView("cloudnest_customer_master")
df_contracts.createOrReplaceTempView("cloudnest_contracts")
df_usage_logs.createOrReplaceTempView("cloudnest_usage_logs")
df_support_tickets.createOrReplaceTempView("cloudnest_support_tickets")
df_billing.createOrReplaceTempView("cloudnest_billing")

print("\nテンポラリビューを登録しました:")
print(" - cloudnest_customer_master / cloudnest_contracts / cloudnest_usage_logs")
print(" - cloudnest_support_tickets / cloudnest_billing")
print("\n次のノートブック（02_bronze_ingestion.py）で Delta テーブルとして保存してください。")
# spark.stop() はここで呼ばない（Databricks クラスターが管理するため）

"""事前生成済みLLM回答（`pre_generated`）フォールバック用フィクスチャの作成。

Databricks Free Edition環境でLLMエンドポイントが未設定・利用不可の場合に備え、
少数の代表的な顧客（高・中・低リスクから2件ずつ）について、あらかじめ作成した
回答を `artifacts/pre_generated_recommendations.json` として保存する。

ここでの回答本文は、開発時にLLM（Claude Code）が実際の顧客360・予測結果・
社内ナレッジを踏まえて作成したものであり、「事前生成済みLLM回答」という
表示に偽りはない。全60顧客分は用意していないため、対象外の顧客は
ルールベース生成（`backend/services/rule_based_generator.py`）にフォールバックする。

実行方法:
    python scripts/generate_pregenerated_recommendations.py

前提:
    artifacts/customer360.json, artifacts/predictions.json が生成済みであること。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT_DIR / "artifacts"

GENERATION_MODE = "pre_generated"
GENERATION_MODE_LABEL = "事前生成済みLLM回答"
MODEL_VERSION = "pre-generated-v1"

# 手作業（開発時のLLMによる作成）で用意した回答。
# customer_id・数値・施策名は artifacts/customer360.json, predictions.json の実データに一致させている。
PRE_GENERATED_CONTENT: dict[str, dict] = {
    "C059": {
        "summary": (
            "顧客059はEC・QR決済・カードの3サービスを継続利用してきましたが、"
            "直近でQR決済の利用が完全に止まり、EC・カードも前期比で2〜3割ほど利用が落ち込んでいます。"
            "過去のEC再訪施策は開封のみで反応がなく、利用サービス数も4→3に減少しています。"
        ),
        "actions": [
            {
                "title": "複数サービスをまたぐ軽量なポイント施策",
                "reason": "QR決済が完全に停止し、EC・カードも同時に低下しているため、単一施策よりも複数サービスをまたぐ軽量な施策の方が状況に合っています。",
            },
            {
                "title": "QR決済の利用メリット案内",
                "reason": "QR決済の利用が直近で完全に止まっているため、再開のきっかけとして利用メリットを案内する余地があります。",
            },
            {
                "title": "施策を行わず経過観察",
                "reason": "過去のEC再訪施策への反応が乏しかったことを踏まえると、追加の連絡を急がず状況を見極める選択も妥当です。",
            },
        ],
        "cautions": [
            "過去のEC施策への反応が弱いため、同種の案内を繰り返すよりも別アプローチか経過観察を検討してください。",
            "本回答は事前に作成された参考情報であり、最新の状況を保証するものではありません。",
        ],
        "reference_doc_ids": ["kb-cross-service", "kb-qr-incentive", "kb-ec-revisit", "kb-support-policy"],
    },
    "C017": {
        "summary": (
            "顧客017はQR決済の利用が直近で完全に止まり、EC・カードも前期比で3割弱ずつ低下しています。"
            "利用サービス数も3→2に減少しました。過去のQR決済ポイント還元施策は開封のみで、"
            "直接の反応には至っていません。"
        ),
        "actions": [
            {
                "title": "複数サービスをまたぐ軽量なポイント施策",
                "reason": "QR決済の停止とEC・カードの同時低下が重なっているため、単一サービスの案内より横断的な軽量施策が状況に合います。",
            },
            {
                "title": "EC再利用の案内",
                "reason": "ECの購入額が前期比-27%と大きく低下しているため、再訪を促す案内が候補になります。",
            },
            {
                "title": "施策を行わず経過観察",
                "reason": "過去のQR施策の反応が乏しいことに加え、直近の問い合わせ内容（利用方法）を踏まえ、まずは状況を見極める選択も考えられます。",
            },
        ],
        "cautions": [
            "過去のQR施策への反応が弱いため、同種の案内を繰り返す前に状況の変化を確認してください。",
            "本回答は事前に作成された参考情報であり、最新の状況を保証するものではありません。",
        ],
        "reference_doc_ids": ["kb-cross-service", "kb-ec-revisit", "kb-qr-incentive", "kb-support-policy"],
    },
    "C015": {
        "summary": (
            "顧客015はEC・QR決済・カードいずれも前期比1〜2割ほど緩やかに利用が低下していますが、"
            "利用サービス数自体は維持されています。直近の複数サービス横断ポイント施策には反応がありませんでした。"
        ),
        "actions": [
            {
                "title": "EC再利用の案内",
                "reason": "ECの購入額が前期比-16%とやや低下しているため、再訪を促す案内が候補になります。",
            },
            {
                "title": "QR決済の利用メリット案内",
                "reason": "QR決済も同程度に低下しているため、EC施策と合わせて案内する余地があります。",
            },
            {
                "title": "施策を行わず経過観察",
                "reason": "直近の横断ポイント施策に反応がなかったため、続けて別施策を案内するより、変化を見極める期間を置くことも選択肢です。",
            },
        ],
        "cautions": [
            "直近の施策に反応がなかったため、同種の施策を続けて案内することは避けてください。",
            "本回答は事前に作成された参考情報であり、最新の状況を保証するものではありません。",
        ],
        "reference_doc_ids": ["kb-ec-revisit", "kb-qr-incentive", "kb-cross-service", "kb-support-policy"],
    },
    "C045": {
        "summary": (
            "顧客045はEC・QR決済・カード・銀行の4サービスすべてで前期比1〜2割程度の緩やかな低下が"
            "見られますが、利用サービス数は維持されています。直近のカード利用特典案内には反応がありませんでした。"
        ),
        "actions": [
            {
                "title": "複数サービスをまたぐ軽量なポイント施策",
                "reason": "特定のサービスだけでなく4サービス全体で同程度の低下が見られるため、横断的な軽量施策が状況に合っています。",
            },
            {
                "title": "QR決済の利用メリット案内",
                "reason": "QR決済とカードの低下幅が大きいため、利用メリットを案内する余地があります。",
            },
            {
                "title": "施策を行わず経過観察",
                "reason": "直近のカード施策への反応がなかったことを踏まえ、続けて別の案内を行うより経過を見る選択も妥当です。",
            },
        ],
        "cautions": [
            "直近のカード施策に反応がなかったため、同種の案内を繰り返すことは避けてください。",
            "本回答は事前に作成された参考情報であり、最新の状況を保証するものではありません。",
        ],
        "reference_doc_ids": ["kb-cross-service", "kb-qr-incentive", "kb-card-benefit", "kb-support-policy"],
    },
    "C010": {
        "summary": (
            "顧客010はEC・銀行の2サービスを利用しており、ECの購入額が前期比-14%とやや低下していますが、"
            "深刻な低下ではありません。過去の施策配信履歴はなく、最近キャンペーン内容についての問い合わせがありました。"
        ),
        "actions": [
            {
                "title": "EC再利用の案内",
                "reason": "ECの購入額がやや低下しているため、軽い再訪案内が候補になります。",
            },
            {
                "title": "施策を行わず経過観察",
                "reason": "低下幅は大きくなく、休眠確率も低リスクの範囲であるため、まずは経過観察とすることが妥当です。",
            },
        ],
        "cautions": [
            "低リスクのため、過度な施策よりも軽い案内か経過観察を優先してください。",
            "本回答は事前に作成された参考情報であり、最新の状況を保証するものではありません。",
        ],
        "reference_doc_ids": ["kb-ec-revisit", "kb-support-policy"],
    },
    "C031": {
        "summary": (
            "顧客031はEC・QR決済とも前期比1割強の緩やかな低下ですが、直近のQR決済ポイント還元施策には"
            "反応があり、関係は良好です。過去に決済エラーの問い合わせも見られるため、利用体験の面での"
            "フォローも有効と考えられます。"
        ),
        "actions": [
            {
                "title": "QR決済の利用メリット案内",
                "reason": "直近のQR決済ポイント還元施策に反応があったため、継続的な利用メリットの案内が効果的である可能性があります。",
            },
            {
                "title": "施策を行わず経過観察",
                "reason": "直近で施策を配信済みであり、過去の決済エラー相談を踏まえると、まずは利用体験の状況を見極めることも選択肢です。",
            },
        ],
        "cautions": [
            "過去に決済エラーの相談があるため、施策の案内より先に利用体験の状況を確認することが望ましい場合があります。",
            "本回答は事前に作成された参考情報であり、最新の状況を保証するものではありません。",
        ],
        "reference_doc_ids": ["kb-qr-incentive", "kb-support-policy"],
    },
}

DOC_TITLES = {
    "kb-ec-revisit": "EC再訪促進メールの施策概要",
    "kb-qr-incentive": "QR決済ポイント還元施策の概要",
    "kb-card-benefit": "カード利用特典案内の施策概要",
    "kb-cross-service": "複数サービス横断ポイント施策の概要",
    "kb-service-overview": "サービス情報（EC・QR決済・カード・ネット銀行・ポイント）",
    "kb-support-policy": "顧客対応方針",
}


def main() -> None:
    generated_at = datetime.now(timezone.utc).isoformat()

    recommendations = {}
    for customer_id, content in PRE_GENERATED_CONTENT.items():
        references = [
            {"doc_id": doc_id, "title": DOC_TITLES[doc_id], "type": "knowledge"}
            for doc_id in content["reference_doc_ids"]
        ]
        recommendations[customer_id] = {
            "customer_id": customer_id,
            "generation_mode": GENERATION_MODE,
            "generation_mode_label": GENERATION_MODE_LABEL,
            "model_version": MODEL_VERSION,
            "generated_at": generated_at,
            "summary": content["summary"],
            "actions": content["actions"],
            "cautions": content["cautions"],
            "references": references,
        }

    output = {
        "model_version": MODEL_VERSION,
        "generated_at": generated_at,
        "recommendations": recommendations,
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ARTIFACTS_DIR / "pre_generated_recommendations.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"事前生成済み回答を生成しました: {output_path}")
    print(f"  対象顧客数: {len(recommendations)} / 60")


if __name__ == "__main__":
    main()

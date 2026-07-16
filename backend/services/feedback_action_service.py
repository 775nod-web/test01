"""施策結果から「次に取る改善アクション」を決定論的なルールで導出する。

Step 6「フィードバック概要」を結果確認だけで終わらせず、続ける施策・見直す施策・
次に検証する内容を判断できるようにするための、デモ用の説明可能なルールベース実装。
外部LLMや機械学習モデルは使わず、担当者判断・施策実施状況・顧客の反応・利用再開状況
から、固定カテゴリの推奨アクションを常に同じ規則で決定する。
"""

from __future__ import annotations

from typing import Optional

ACTION_TYPE_EXPAND = "類似顧客へ展開"
ACTION_TYPE_CHANGE_OFFER = "オファー内容を変更"
ACTION_TYPE_CHANGE_CHANNEL = "接触チャネルを変更"
ACTION_TYPE_CHANGE_TIMING = "接触タイミングを変更"
ACTION_TYPE_REVIEW_TARGETING = "対象顧客の条件を見直す"
ACTION_TYPE_CONTINUE_OBSERVATION = "継続観測"
ACTION_TYPE_REVERIFY_EFFECT = "施策効果を再検証"
ACTION_TYPE_STOP = "今回の施策を停止"

# 「反応あり」とみなす施策後の反応（メール開封等は弱い反応も含めて反応ありとして扱う）
ENGAGED_RESPONSES = {"メール開封", "案内ページ閲覧", "クーポン利用", "問い合わせ"}
# 「利用再開あり」とみなす利用状況
RECOVERED_STATUSES = {"30日以内に利用再開", "一部サービスで利用再開"}

# Step 6の全体サマリーで「継続・展開候補」に分類するアクション種別
EXPAND_TYPES = {ACTION_TYPE_EXPAND}
# 「見直し候補」に分類するアクション種別
REVIEW_TYPES = {
    ACTION_TYPE_CHANGE_OFFER,
    ACTION_TYPE_CHANGE_CHANNEL,
    ACTION_TYPE_CHANGE_TIMING,
    ACTION_TYPE_REVIEW_TARGETING,
    ACTION_TYPE_STOP,
}
# 「次回検証する仮説」に分類するアクション種別
HYPOTHESIS_TYPES = {ACTION_TYPE_CONTINUE_OBSERVATION, ACTION_TYPE_REVERIFY_EFFECT}


def _build(action_type: str, label: str, reason: str, next_review_timing: str) -> dict:
    return {
        "type": action_type,
        "label": label,
        "reason": reason,
        "next_review_timing": next_review_timing,
    }


def determine_next_action(
    *,
    decision: Optional[str],
    selected_action: Optional[str],
    comment: Optional[str],
    campaign_status: str,
    customer_response: str,
    usage_recovery_status: str,
) -> dict:
    """担当者判断・施策実施状況・顧客の反応・利用再開状況から推奨アクションを決定する。

    未知の値・欠損値が渡された場合も例外を送出せず、安全な既定値（継続観測）へ
    フォールバックする。同じ入力に対しては常に同じ結果を返す（副作用・乱数なし）。
    """
    if decision == "skipped":
        reason = "見送りと判断されたため、見送り理由を次回の対象顧客の選定条件へ反映します。"
        if comment:
            reason = f"{reason}（コメント：{comment}）"
        return _build(
            ACTION_TYPE_REVIEW_TARGETING,
            "見送り理由を次回の対象条件に反映",
            reason,
            "次回の対象選定時に見直し",
        )

    if usage_recovery_status == "観測期間中":
        reason = f"{customer_response or '反応'}は確認できていますが、利用再開の判定にはまだ時間が必要なため観測を継続します。"
        return _build(
            ACTION_TYPE_CONTINUE_OBSERVATION,
            "継続して観測",
            reason,
            "30日後に再確認",
        )

    if campaign_status == "施策未実施" or customer_response == "施策未実施" or usage_recovery_status == "施策未実施":
        return _build(
            ACTION_TYPE_CONTINUE_OBSERVATION,
            "施策実施前のため観測を継続",
            "施策自体がまだ実施されていないため、まずは観測を継続します。",
            "施策実施後に再確認",
        )

    engaged = customer_response in ENGAGED_RESPONSES
    recovered = usage_recovery_status in RECOVERED_STATUSES

    if engaged and recovered:
        reason = f"{customer_response}の後に{usage_recovery_status}となったため、有効な施策として同様の利用低下パターンを持つ顧客への展開を検討します。"
        result = _build(
            ACTION_TYPE_EXPAND,
            "同様の利用低下パターンを持つ顧客への展開候補",
            reason,
            "30日後に継続利用を確認",
        )
    elif engaged and not recovered:
        reason = f"{customer_response}はありましたが利用再開には至らなかったため、オファー内容や案内導線の見直しを検討します。"
        result = _build(
            ACTION_TYPE_CHANGE_OFFER,
            "オファー内容や導線の見直し候補",
            reason,
            "14日後に反応を再確認",
        )
    elif (not engaged) and (not recovered):
        reason = "反応が確認できず利用再開もなかったため、別チャネルまたは別の施策への切り替えを検討します。"
        result = _build(
            ACTION_TYPE_CHANGE_CHANNEL,
            "別チャネルでの接触候補",
            reason,
            "14日後に新チャネルでの反応を確認",
        )
    else:
        reason = "反応は確認できませんでしたが利用が再開しているため、自然回復の可能性を考慮し施策効果を再検証します。"
        result = _build(
            ACTION_TYPE_REVERIFY_EFFECT,
            "施策効果の再検証候補",
            reason,
            "30日後に自然回復かどうかを再検証",
        )

    if decision == "modified":
        note = (
            f"修正内容（{selected_action}）を有効施策の条件として記録します。"
            if selected_action
            else "修正内容を有効施策の条件として記録します。"
        )
        result["reason"] = f"{result['reason']}{note}"
    elif decision == "approved":
        result["reason"] = f"{result['reason']}承認済みの施策として次回の施策評価に活用します。"

    return result


def build_improvement_summary(sample_outcomes: list[dict]) -> dict:
    """複数顧客の推奨アクションから、Step 6下部の全体サマリー3項目を組み立てる。

    件数が0件の場合は無理に文章を生成せず、全項目をNoneのまま返す
    （呼び出し側・UIで「十分な結果がありません」を表示する）。
    """
    expand = [o for o in sample_outcomes if o["recommended_next_action"]["type"] in EXPAND_TYPES]
    review = [o for o in sample_outcomes if o["recommended_next_action"]["type"] in REVIEW_TYPES]
    hypothesis = [o for o in sample_outcomes if o["recommended_next_action"]["type"] in HYPOTHESIS_TYPES]

    expand_candidates = None
    if expand:
        first = expand[0]
        expand_candidates = (
            f"{first['customer_response']}で利用再開が確認できた施策は、"
            "同様の利用低下パターンを持つ顧客への展開を検討します。"
        )

    review_candidates = None
    if review:
        first = review[0]
        review_candidates = (
            f"{first['customer_response']}だった施策は、"
            f"{first['recommended_next_action']['label']}を検討します。"
        )

    next_hypothesis = None
    if hypothesis:
        first = hypothesis[0]
        first_type = first["recommended_next_action"]["type"]
        if first_type == ACTION_TYPE_REVERIFY_EFFECT:
            next_hypothesis = (
                f"{first['customer_response']}でも利用が再開したケースがあり、"
                "施策効果自体が本当にあったのかを次回検証します。"
            )
        else:
            next_hypothesis = "観測期間中または施策未実施の顧客について、十分な期間をおいてから利用再開の有無を次回検証します。"

    return {
        "expand_candidates": expand_candidates,
        "review_candidates": review_candidates,
        "next_hypothesis": next_hypothesis,
    }

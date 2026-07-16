import { useEffect, useState } from "react";
import { postDecision } from "../api/client";
import type { DecisionType, RecommendationResponse } from "../types";

const GENERATION_MODE_BADGE_CLASS: Record<string, string> = {
  llm: "badge badge--databricks",
  pre_generated: "badge badge--demo",
  rule_based: "badge",
};

const DECISION_LABEL: Record<DecisionType, string> = {
  approved: "承認",
  modified: "修正",
  skipped: "見送り",
};

interface Props {
  customerId: string;
  recommendation: RecommendationResponse;
  onDecisionSaved: () => void;
}

type SaveState = "idle" | "saving" | "saved" | "error";

function formatGeneratedAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString("ja-JP");
  } catch {
    return iso;
  }
}

export function RecommendationPanel({ customerId, recommendation, onDecisionSaved }: Props) {
  const [decisionType, setDecisionType] = useState<DecisionType | null>(null);
  const [selectedActionTitle, setSelectedActionTitle] = useState<string | null>(null);
  const [modifiedText, setModifiedText] = useState("");
  const [comment, setComment] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // 顧客が変わったら入力状態をリセットする
  useEffect(() => {
    setDecisionType(null);
    setSelectedActionTitle(null);
    setModifiedText("");
    setComment("");
    setSaveState("idle");
    setErrorMessage(null);
  }, [customerId]);

  async function handleSave() {
    if (!decisionType) {
      return;
    }
    setSaveState("saving");
    setErrorMessage(null);
    try {
      await postDecision(customerId, {
        decision: decisionType,
        selected_action: selectedActionTitle,
        modified_text: decisionType === "modified" ? modifiedText : null,
        comment: comment || null,
        generation_mode: recommendation.generation_mode,
        model_version: recommendation.model_version,
      });
      setSaveState("saved");
      onDecisionSaved();
    } catch (error) {
      setSaveState("error");
      setErrorMessage(error instanceof Error ? error.message : "不明なエラー");
    }
  }

  if (saveState === "saved") {
    return (
      <div className="recommendation-panel">
        <div className="recommendation-panel__saved">
          <span aria-hidden="true">✅</span>
          <div>
            <p className="recommendation-panel__saved-title">
              判断を記録しました（{DECISION_LABEL[decisionType ?? "skipped"]}）
            </p>
            <p className="recommendation-panel__saved-sub">
              フィードバック概要に反映されました。他の顧客を選択して続けられます。
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="recommendation-panel">
      <p className="recommendation-panel__summary">{recommendation.summary}</p>

      <div className="recommendation-panel__actions">
        {recommendation.actions.map((action) => (
          <label key={action.title} className="recommendation-panel__action">
            <input
              type="radio"
              name="selected-action"
              checked={selectedActionTitle === action.title}
              onChange={() => setSelectedActionTitle(action.title)}
            />
            <span>
              <span className="recommendation-panel__action-title">{action.title}</span>
              <span className="recommendation-panel__action-reason">{action.reason}</span>
            </span>
          </label>
        ))}
      </div>

      {recommendation.cautions.length > 0 && (
        <ul className="recommendation-panel__cautions">
          {recommendation.cautions.map((caution) => (
            <li key={caution}>{caution}</li>
          ))}
        </ul>
      )}

      <div className="recommendation-panel__references">
        参照元:{" "}
        {recommendation.references.map((ref) => ref.title).join(" / ") || "なし"}
      </div>

      <p className="recommendation-panel__footnote">
        <span className={GENERATION_MODE_BADGE_CLASS[recommendation.generation_mode] ?? "badge"}>
          {recommendation.generation_mode_label}
        </span>{" "}
        モデルバージョン {recommendation.model_version} ・ 生成日時{" "}
        {formatGeneratedAt(recommendation.generated_at)}
      </p>

      <div className="recommendation-panel__decision">
        <div className="recommendation-panel__decision-buttons">
          {(Object.keys(DECISION_LABEL) as DecisionType[]).map((type) => (
            <button
              key={type}
              type="button"
              className={
                decisionType === type
                  ? "decision-button decision-button--selected"
                  : "decision-button"
              }
              onClick={() => setDecisionType(type)}
            >
              {DECISION_LABEL[type]}
            </button>
          ))}
        </div>

        {decisionType === "modified" && (
          <textarea
            className="recommendation-panel__textarea"
            placeholder="修正後のアクション内容を入力してください"
            value={modifiedText}
            onChange={(e) => setModifiedText(e.target.value)}
          />
        )}

        <textarea
          className="recommendation-panel__textarea"
          placeholder="コメント（任意）"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />

        {errorMessage && <p className="panel__status panel__status--error">{errorMessage}</p>}

        <button
          type="button"
          className="recommendation-panel__save-button"
          disabled={!decisionType || saveState === "saving"}
          onClick={() => void handleSave()}
        >
          {saveState === "saving" ? "保存中..." : "判断を保存"}
        </button>
      </div>
    </div>
  );
}

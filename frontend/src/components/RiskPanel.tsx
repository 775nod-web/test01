import type { Prediction } from "../types";
import { RiskBadge } from "./RiskBadge";

const MODEL_MODE_LABEL: Record<string, string> = {
  trained: "実学習モデル",
  precomputed: "事前計算済み予測",
};

function formatInferenceAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString("ja-JP");
  } catch {
    return iso;
  }
}

export function RiskPanel({
  prediction,
  modelMode,
}: {
  prediction: Prediction;
  modelMode: string;
}) {
  return (
    <div className="risk-panel">
      <div className="risk-panel__headline">
        <RiskBadge band={prediction.risk_band} label={prediction.risk_band_label} />
        <span className="risk-panel__probability">
          休眠確率 {Math.round(prediction.churn_probability * 100)}%
        </span>
      </div>

      <ul className="risk-panel__reasons">
        {prediction.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>

      <p className="risk-panel__footnote">
        {MODEL_MODE_LABEL[modelMode] ?? modelMode} ・ モデルバージョン {prediction.model_version} ・
        推論日時 {formatInferenceAt(prediction.inference_at)}
      </p>
    </div>
  );
}

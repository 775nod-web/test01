import { useState, type FormEvent } from "react";
import { ApiError, postCaseDecision } from "../../api";
import type { DecisionResponse, InvestigationResult } from "../../types";

interface DecisionFormProps {
  transactionId: string;
  initialResult: InvestigationResult | null;
  initialMemo: string | null;
  onSuccess: (response: DecisionResponse) => void;
}

const RESULT_OPTIONS: InvestigationResult[] = ["不正", "正常", "追加確認"];

function DecisionForm({ transactionId, initialResult, initialMemo, onSuccess }: DecisionFormProps) {
  const [result, setResult] = useState<InvestigationResult | null>(initialResult);
  const [memo, setMemo] = useState(initialMemo ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!result) {
      setErrorMessage("調査結果(不正・正常・追加確認のいずれか)を選択してください。");
      return;
    }
    setSubmitting(true);
    setErrorMessage("");
    postCaseDecision(transactionId, { result, memo: memo.trim() || undefined })
      .then((response) => {
        onSuccess(response);
      })
      .catch((error: unknown) => {
        setErrorMessage(error instanceof ApiError ? error.message : "調査結果の登録に失敗しました。");
      })
      .finally(() => {
        setSubmitting(false);
      });
  }

  return (
    <section className="card" aria-labelledby="decision-form-heading">
      <h2 id="decision-form-heading">調査結果入力</h2>
      <form onSubmit={handleSubmit}>
        <fieldset className="decision-fieldset">
          <legend>調査結果</legend>
          <div className="decision-options" role="radiogroup" aria-label="調査結果">
            {RESULT_OPTIONS.map((option) => (
              <label key={option} className="decision-option">
                <input
                  type="radio"
                  name="investigation-result"
                  value={option}
                  checked={result === option}
                  onChange={() => setResult(option)}
                />
                {option}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="filter-field filter-field-grow">
          <label htmlFor="decision-memo">調査メモ（任意）</label>
          <textarea
            id="decision-memo"
            rows={3}
            maxLength={500}
            value={memo}
            onChange={(e) => setMemo(e.target.value)}
            placeholder="調査の経緯や判断理由を記録できます(任意)"
          />
        </div>

        {errorMessage && (
          <p className="form-error" role="alert">
            {errorMessage}
          </p>
        )}

        <button type="submit" disabled={submitting}>
          {submitting ? "登録中…" : "調査結果を登録"}
        </button>
      </form>

      <p className="meta-line" style={{ marginTop: 12 }}>
        この結果はセッション内のみ保持され、モデル改善へのフィードバックを模したものです。実際の決済制御は行われません。
      </p>
    </section>
  );
}

export default DecisionForm;

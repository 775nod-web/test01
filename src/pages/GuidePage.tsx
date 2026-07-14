import { Link } from "react-router-dom";

const STEPS = [
  { title: "概況画面で「既存ルールのみ」を表示", detail: "概況ダッシュボードを開き、判定方式が「既存ルールのみ」になっていることを確認します。" },
  { title: "正常承認率と誤検知率を確認", detail: "上段KPIの正常取引承認率・誤検知率に注目し、既存ルールだけでは正常な顧客も一定数止めてしまっていることを伝えます。" },
  { title: "「ルール＋AI」へ切り替え", detail: "判定方式フィルターを「ルール＋AI」に切り替えます。" },
  { title: "改善の経営インパクトを説明", detail: "不正捕捉率を大きく落とさずに、正常承認率が上がり誤検知率が下がることを比較カードとKPIで示します。" },
  { title: "TXN-100123を開く", detail: "高リスク取引一覧の先頭に固定表示されているTXN-100123の行を選択し、調査詳細画面へ遷移します。" },
  { title: "複数要因を確認", detail: "「なぜ確認が必要か」セクションで、新規端末・深夜帯・短時間連続取引・地域乖離・金額超過という複数のリスク要因が重なって判断されていることを確認します。" },
  { title: "調査結果を登録", detail: "画面下部の調査結果入力から、不正・正常・追加確認のいずれかを選択して登録し、トースト通知とステータス更新を確認します。" },
  { title: "判定根拠と監査情報を確認", detail: "既存ルール該当理由、AIスコア上位要因、モデルバージョン、操作履歴（デモ用監査情報）を確認します。" },
];

const MESSAGES = [
  "不正率だけを最適化すると、正常な顧客を止めてしまう可能性があります。",
  "ルールとAIの組み合わせにより、不正損失と顧客体験を同時に管理できます。",
  "調査担当者は情報収集ではなく、判断そのものに時間を使えるようになります。",
  "調査結果を将来の検知改善へフィードバックする仕組みを想定しています。",
  "本番導入前のPoCでは、実際の顧客データを用いて経済価値を検証します。",
];

function GuidePage() {
  return (
    <div className="guide-page">
      <div className="page-header">
        <h1>デモガイド</h1>
        <p className="page-description">
          このデモは約10分で、経営判断・調査判断・説明責任の3つの観点を一連の流れで体験できます。
        </p>
      </div>

      <section className="card" aria-labelledby="steps-heading">
        <h2 id="steps-heading">10分デモの進め方</h2>
        <ol className="guide-steps">
          {STEPS.map((step, index) => (
            <li key={step.title}>
              <span className="guide-step-number">{index + 1}</span>
              <div>
                <p className="guide-step-title">{step.title}</p>
                <p className="guide-step-detail">{step.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="card" aria-labelledby="messages-heading">
        <h2 id="messages-heading">話すメッセージ</h2>
        <ul>
          {MESSAGES.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      </section>

      <section className="card" aria-labelledby="quick-links-heading">
        <h2 id="quick-links-heading">クイックリンク</h2>
        <p>
          <Link to="/">概況ダッシュボードを開く</Link>
          {" ／ "}
          <Link to="/cases/TXN-100123">代表ケース(TXN-100123)の調査詳細を開く</Link>
          {" ／ "}
          <Link to="/cases">調査ケース一覧を開く</Link>
        </p>
      </section>
    </div>
  );
}

export default GuidePage;

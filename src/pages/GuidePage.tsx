import { Link } from "react-router-dom";

function GuidePage() {
  return (
    <div className="guide-page">
      <div className="page-header">
        <h1>デモガイド</h1>
        <p className="page-description">10分デモの進め方と、話すメッセージの詳細ガイドはPhase 3で実装予定です。</p>
      </div>
      <div className="card phase-note">
        <p>現時点で体験できる操作:</p>
        <ul>
          <li>
            <Link to="/">概況ダッシュボード</Link>
            で、期間・判定方式・チャネルを切り替えてKPIやグラフの変化を確認する。
          </li>
          <li>
            <Link to="/">概況ダッシュボード</Link>
            の高リスク取引一覧、または
            <Link to="/cases">調査ケース</Link>
            一覧から代表ケース(TXN-100123)を開き、リスク要因と判定根拠を確認する。
          </li>
        </ul>
        <p>調査結果の登録機能を含む完全なデモガイドはPhase 3で追加します。</p>
      </div>
    </div>
  );
}

export default GuidePage;

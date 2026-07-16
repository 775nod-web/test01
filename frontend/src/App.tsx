import { useEffect, useState } from "react";
import "./App.css";
import { fetchHealth, fetchMetadata } from "./api/client";
import type { MetadataResponse } from "./types";

type LoadState =
  | { status: "loading" }
  | { status: "ready"; metadata: MetadataResponse }
  | { status: "error"; message: string };

const DATA_MODE_LABEL: Record<string, string> = {
  demo: "合成データ（demo）",
  databricks: "Databricks接続",
};

function formatUpdatedAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString("ja-JP");
  } catch {
    return iso;
  }
}

function HeaderMeta({ state }: { state: LoadState }) {
  if (state.status === "loading") {
    return <span className="header__meta">読み込み中...</span>;
  }
  if (state.status === "error") {
    return (
      <span className="header__meta">
        <span className="badge badge--error">API未接続</span>
        {state.message}
      </span>
    );
  }
  const { metadata } = state;
  const badgeClass =
    metadata.data_mode === "databricks" ? "badge badge--databricks" : "badge badge--demo";
  return (
    <span className="header__meta">
      <span className={badgeClass}>{DATA_MODE_LABEL[metadata.data_mode] ?? metadata.data_mode}</span>
      <span>最終更新: {formatUpdatedAt(metadata.updated_at)}</span>
    </span>
  );
}

export default function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        await fetchHealth();
        const metadata = await fetchMetadata();
        if (!cancelled) {
          setState({ status: "ready", metadata });
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "不明なエラー";
          setState({ status: "error", message });
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="app">
      <header className="header">
        <h1 className="header__title">顧客休眠予兆・次アクション支援デモ</h1>
        <HeaderMeta state={state} />
      </header>

      <main className="layout">
        <section className="panel" aria-label="本日の優先顧客">
          <h2 className="panel__title">本日の優先顧客</h2>
          <div className="empty-state">
            <span className="empty-state__icon" aria-hidden="true">
              📋
            </span>
            <p className="empty-state__text">
              顧客一覧は次フェーズでDatabricksデータ層と接続します。
              <br />
              現時点ではAPIの土台のみが用意されています。
            </p>
          </div>
        </section>

        <section className="panel panel--stacked" aria-label="顧客360と休眠リスク">
          <div>
            <h2 className="panel__title">顧客360</h2>
            <div className="empty-state">
              <span className="empty-state__icon" aria-hidden="true">
                📊
              </span>
              <p className="empty-state__text">
                顧客を選択すると、EC・QR決済・カードなど複数サービスの利用推移が表示されます。
              </p>
            </div>
          </div>
          <div>
            <h2 className="panel__title">休眠リスク</h2>
            <div className="empty-state">
              <span className="empty-state__icon" aria-hidden="true">
                🔍
              </span>
              <p className="empty-state__text">
                休眠確率、リスク帯、主要な予測理由はLayer 2実装後に表示されます。
              </p>
            </div>
          </div>
        </section>

        <section className="panel" aria-label="次のアクション">
          <h2 className="panel__title">次のアクション</h2>
          <div className="empty-state">
            <span className="empty-state__icon" aria-hidden="true">
              💡
            </span>
            <p className="empty-state__text">
              推奨アクション、根拠、参照元、承認・修正・見送りの操作はLayer 3実装後に表示されます。
            </p>
          </div>
        </section>
      </main>

      <footer className="footer">
        フィードバックループと本番化時の追加事項は、Step 6実装時にこの領域へ表示します。
      </footer>
    </div>
  );
}

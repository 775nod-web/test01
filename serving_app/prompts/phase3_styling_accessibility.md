# Phase 3: 配色・アクセシビリティの仕上げ

## 目的

「Google流のスライド作成術で使われるような淡い鮮やかな色」という要件を、
勘やeyeballingではなく検証可能な形で満たす。

## やること

1. `dataviz` skill を読み込み、手順（form → color → validate → marks →
   interaction → accessibility）に従う。
2. カテゴリ配色を7スロット、Google Slidesの「Light 2」系統に近い
   青・赤・金/黄・緑・紫・橙・青緑で仮決めする。
3. `node scripts/validate_palette.js "<hex,...>" --mode light` と
   `--mode dark` の両方を実行し、以下4項目がすべてPASSするまで調整する
   （目視で決めない）。
   - Lightness band
   - Chroma floor
   - CVD separation
   - Contrast vs surface（WARNの場合は直接ラベル or 表表示で緩和する）
4. 検証済みの値を `frontend/src/theme.css` にCSSカスタムプロパティとして
   light/dark両方定義する。`prefers-color-scheme` をデフォルトの合図とし、
   `[data-theme="light"]` / `[data-theme="dark"]` の明示指定がそれを上書き
   できるようにする。
5. アクセシビリティの最終チェック:
   - 2系列以上のチャートには凡例を必ず表示する
   - 色だけに意味を持たせない（数値ラベル・アイコン・テキストを併記）
   - 状態色（warning/critical）はカテゴリ配色と別枠にし、アイコン＋ラベルで
     表現する（`UnregisteredMasterReportPanel` のバッジ参照）
   - 表表示（テーブルビュー）がグラフの代替として存在する
     （`StoreRankingPanel` のグラフ/表切り替え参照）

## 完了確認

- 両モードの `validate_palette.js` がALL CHECKS PASSになること。
- ブラウザ（またはビルド結果）でライト/ダーク切り替えボタンを操作し、
  レイアウト崩れやコントラスト不足が無いことを目視確認する。

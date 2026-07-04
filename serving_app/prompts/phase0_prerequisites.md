# Phase 0: 前提確認

このアプリを構築・再構築する前に、以下を確認してください。

## 確認事項

1. Gold layerの4表がDatabricks上に存在すること
   - `gold.gold_daily_store_sales`
   - `gold.gold_category_sales`
   - `gold.gold_store_ranking`
   - `gold.gold_unregistered_master_report`
   - 存在しない場合は、リポジトリ直下の `populate_retail_gold_layer_tables.py`
     までの一連のスクリプト（generate → sample → bronze → silver → gold）を
     Databricksノートブックで実行して作成する。
2. 接続先はServerless Starter Warehouse（Warehouse ID: `50153ad923fecd73`）。
   このWarehouseが起動可能な状態であること。
3. デプロイ先はDatabricks Appsのみ。ローカル・他クラウドへの恒久デプロイは行わない。
4. **Databricks Appsの上限に達しても、他ユーザーが作成したアプリを自動的に
   削除しない。** 上限に達した場合は人間に確認を取る（`CLAUDE.md` 参照）。

## このフェーズのゴール

- 上記の前提が揃っていることを確認するのみ。コードの変更は行わない。
- 揃っていない場合は、何が欠けているかを明示して次のフェーズに進まない。

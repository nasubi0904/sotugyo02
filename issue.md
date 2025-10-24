# issue.md

## 2024-XX-XX タイムラインオーバーレイ初期化エラー
- 現象: NodeEditorWindow の初期化時に `TimelineGridOverlay` に `set_column_units` が存在せず `AttributeError` が発生する。
- 原因: `TimelineGridOverlay` クラスでは列単位を設定するメソッド名が `set_units` のまま実装されており、ウィンドウ側の期待する `set_column_units` と不一致だった。
- 対応: `TimelineGridOverlay` に互換メソッド `set_column_units` を追加し、内部で既存の `set_units` を呼び出すことで例外を解消。

# issue.md

## 2024-XX-XX タイムラインオーバーレイ初期化エラー
- 現象: NodeEditorWindow の初期化時に `TimelineGridOverlay` に `set_column_units` が存在せず `AttributeError` が発生する。
- 原因: `TimelineGridOverlay` クラスでは列単位を設定するメソッド名が `set_units` のまま実装されており、ウィンドウ側の期待する `set_column_units` と不一致だった。
- 対応: `TimelineGridOverlay` に互換メソッド `set_column_units` を追加し、内部で既存の `set_units` を呼び出すことで例外を解消。

## 2025-XX-XX タイムライン背景描画の刷新
- 現象: タイムラインの列区切りと日付ラベルが個別のグラフィックスアイテムでオーバーレイ描画されており、背景色の変更要求に対応しづらかった。
- 原因: 背景やグリッド線を `QGraphicsRectItem` などのシーンアイテムで構成していたため、シーン全体の背景色を直接制御できず、描画コストも高かった。
- 対応: 背景のタイル生成を `QGraphicsView` の背景ブラシで描画する方式に改め、日付境界のグリッド線も同ブラシで統合的に描画するよう変更した。

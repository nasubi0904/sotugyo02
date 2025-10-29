# windows ジャンル概要

このディレクトリには PySide6 を用いた主要ウィンドウとその周辺部品を配置します。

- `controllers/` はウィンドウとドメイン層を仲介するコントローラを集約します。
  - `start.py` はスタート画面のドメイン連携を担うコントローラです。
- `views/` にはトップレベルウィンドウを配置します。
  - `start.py` はアプリ起動時のスタート画面を提供します。
  - `node_editor.py` は NodeGraphQt ベースのノードエディタ画面を表現します。
- `docks/` にはドックウィジェットをまとめます（例: `content_browser.py`, `inspector.py`）。
- `toolbars/` はツールバー実装を格納し、`timeline_alignment.py` がノード整列操作を提供します。
- `backgrounds/` では NodeGraph 背景などの補助的な UI ユーティリティを管理します。

## 編集時の指針
- UI の見た目調整は `ui/style.py` のスタイル定義を活用し、ハードコードされたスタイル値を極力避ける。
- ドメイン層のサービス (`ProjectService`, `UserSettingsManager` など) とは疎結合を維持し、UI はコントローラ経由でアクセスする。
- ウィンドウ間の遷移や状態管理を変更する際は、リソースリーク（ウィンドウの閉じ忘れ）に注意する。

## 依存関係の考慮
- NodeGraphQt コンポーネントを追加する場合は `ui/components` のノード定義を利用する。
- 新しいウィンドウを追加する際は、`__init__.py` にエクスポートを忘れずに追記する。

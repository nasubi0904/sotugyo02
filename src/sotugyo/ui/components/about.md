# components ジャンル概要

このディレクトリには NodeGraphQt で使用するカスタムノードなど、UI 部品のロジックを配置します。

- `nodes/` ディレクトリでノードを種類ごとに分割し、
  - `demo.py` にデモ用ノード (`BaseDemoNode`, `TaskNode`, `ReviewNode`) を、
  - `memo.py` にメモ専用ノード (`MemoNode`) を、
  - `tool_environment.py` にツール環境ノード (`ToolEnvironmentNode`) を定義します。
- `content_browser.py` はノードカタログの UI を提供します。
- 以前存在した `timeline/` 配下のタイムライン表示・スナップ関連コンポーネントは撤去済みです。

## 編集時の指針
- NodeGraphQt の識別子 (`__identifier__`) やポート構成を変更する際は、既存ワークスペースとの互換性に注意する。
- 視覚的なふるまいは必要に応じて `ui/style.py` や NodeGraphQt のスタイル API で調整し、ここではノードの振る舞いロジックに集中する。
- 新しいノードを追加する場合は、エディタでの登録処理が `ui/windows/node_editor_window.py` で行われていることを確認する。

## 依存関係の考慮
- PySide6 ではなく NodeGraphQt の API を主に利用し、他層との依存を最小限に保つ。
- 共通のノード振る舞いは継承階層（例: `BaseDemoNode`）でまとめ、重複コードを避ける。

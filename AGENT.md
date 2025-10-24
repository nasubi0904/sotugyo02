# プロジェクト指針

# 開発ガイドライン
(a) すべての人間が目にする出力（プルリクエスト本文、コメント、チャット応答など）は厳格に日本語で作成すること。

## 確定事項
- 対応ランタイム: **Windows 向け Python 3.11 Embeddable Package** を同梱する。
- GUI フレームワーク: **PySide6**。
- アプリケーションコードは **zipapp (.pyz)** としてパッケージし、同梱ランタイムで実行する。
- 既定ランチャーはコンソールを表示しない `pythonw.exe` で zipapp を起動する。

## 開発ルール
1. リポジトリはソース閲覧や編集がしやすい形を維持し、ドキュメント目的以外のコンパイル済みバイナリはコミットしない。
2. 特別な指示がない限り、これらのルールはリポジトリ全体に適用する。
3. ランタイムやビルド手順・前提条件は `plan.md` などのドキュメントに記録する。
4. Python コードは可能な限り PEP 8 に準拠し、実用的な範囲で型ヒントを付与する。
5. パッケージングスクリプトを変更する際は、スタジオ固有のディレクトリをハードコードせず、環境変数や設定ファイルで経路を調整できるようにする。
6. プレーンテキストのドキュメントや説明は絶対にすべて日本語で記述する。

## 現在のディレクトリ構成（視認性優先）
- `/`
  - `AGENT.md`
  - `plan.md`
  - `src/`
    - `__init__.py`
    - `sotugyo/`
      - `__init__.py`
      - `main.py`
      - `domain/`
        - `__init__.py`
        - `projects/`（`about.md`、`registry.py`、`service.py`、`settings.py`、`structure.py`、`timeline.py`）
        - `tooling/`（`about.md`、`coordinator.py`、`models.py`、`repository.py`、`service.py`、`templates.py`）
        - `users/`（`about.md`、`settings.py`）
      - `infrastructure/`
        - `__init__.py`
        - `paths/`（`about.md`、`storage.py`）
      - `ui/`
        - `__init__.py`
        - `components/`
          - `__init__.py`
          - `content_browser.py`
          - `nodes/`（`__init__.py`、`demo.py`、`memo.py`、`tool_environment.py`）
          - `timeline/`（`__init__.py`、`graph.py`、`snap.py`）
        - `dialogs/`（`__init__.py`、`about.md`、`project_settings_dialog.py`、`tool_environment_dialog.py`、`tool_registry_dialog.py`、`user_settings_dialog.py`）
        - `style.py`
        - `windows/`（`__init__.py`、`about.md`、`node_editor_window.py`、`start_window.py`）
  - `tests/`
    - `domain/`
      - `projects/`（`test_timeline.py`）

※ 構成に変更が生じた場合は本節を随時更新すること。

## ディレクトリ構成ポリシー
- `src/sotugyo/domain/`
  - 業務ロジックをジャンル別に管理する領域。`projects/` はプロジェクト管理、`users/` はユーザー管理に関する機能のみを保持する。
- `src/sotugyo/infrastructure/`
  - ファイルシステムや環境変数など、外部環境とのインターフェースを扱うユーティリティを配置する。`paths/` には設定保存先の解決ロジックを集約する。
- `src/sotugyo/ui/`
  - 画面表現と対話ロジックを担当する層。`windows/`、`dialogs/`、`components/` で役割を分離し、スタイルは `style.py` に集約する。

AI エージェントは担当タスクに紐づくジャンルのディレクトリ内のファイルのみを編集し、関係しないジャンルのファイルやフォルダには変更を加えないこと。
また、作業開始時にどのファイルを編集するか明示すること。

コードの設計編集を行う場合はissue.meを必ず参照し競合やエラーを回避するようにしてください。
ユーザーからコードや設計の修正依頼が来た場合は原因を徹底的に追求しissue.mdにレポートとして追記するようにしてください。

作業開始前にリポジトリ直下の `rule.md` を必ず参照し、設計・実装ルールを確認すること。

ジャンルごとに配置した `about.md` を必ず確認してから該当ディレクトリで作業すること。
- `src/sotugyo/domain/projects/about.md`
- `src/sotugyo/domain/users/about.md`
- `src/sotugyo/infrastructure/paths/about.md`
- `src/sotugyo/ui/windows/about.md`
- `src/sotugyo/ui/components/about.md`
- `src/sotugyo/ui/dialogs/about.md`

## 開発環境情報
- `pip list` の結果（2025-10-21 時点）
  - NodeGraphQt 0.6.43
  - OdenGraphQt 0.7.4
  - packaging 25.0
  - pip 25.2 / setuptools 80.9.0 / wheel 0.45.1
  - PySide6 6.10.0 / PySide6_Addons 6.10.0 / PySide6_Essentials 6.10.0
  - Qt.py 1.4.8
  - QtPy 2.4.3
  - shiboken6 6.10.0
  - types-pyside2 5.15.2.1.7
  - typing_extensions 4.15.0

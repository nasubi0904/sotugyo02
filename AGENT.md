# プロジェクト指針

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

## ディレクトリ構成ポリシー
- `src/sotugyo/domain/`
  - 業務ロジックをジャンル別に管理する領域。`projects/` はプロジェクト管理、`users/` はユーザー管理に関する機能のみを保持する。
- `src/sotugyo/infrastructure/`
  - ファイルシステムや環境変数など、外部環境とのインターフェースを扱うユーティリティを配置する。`paths/` には設定保存先の解決ロジックを集約する。
- `src/sotugyo/ui/`
  - 画面表現と対話ロジックを担当する層。`windows/`、`dialogs/`、`components/` で役割を分離し、スタイルは `style.py` に集約する。

AI エージェントは担当タスクに紐づくジャンルのディレクトリ内のファイルのみを編集し、関係しないジャンルのファイルやフォルダには変更を加えないこと。
また、作業開始時にどのファイルを編集するか明示すること。

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
  - PySide6 6.10.0 / PySide6_Addons 6.10.0 / PySide6_Essentials 6.10.0
  - Qt.py 1.4.8
  - shiboken6 6.10.0
  - types-pyside2 5.15.2.1.7
  - pip 25.2 / setuptools 80.9.0 / wheel 0.45.1

# モジュール調査ノート

本ドキュメントでは、本プロジェクトで利用が予定されている主要モジュールについて、公式ドキュメントや一次情報、信頼できる資料を整理する。開発作業時には最新情報を確認しつつ、ここに記載した参考リンクと注意事項を出発点として調査を継続すること。

## Rez
- **公式ドキュメント**: <https://rez.readthedocs.io/en/stable/>
- **GitHub リポジトリ**: <https://github.com/AcademySoftwareFoundation/rez>
- **概要**: VFX / アニメーション業界で広く利用されるパッケージ管理・環境構築ツール。ソフトウェアごとに独立した実行環境を記述でき、スタジオ内パイプラインの再現性を高められる。
- **主な特徴**:
  - `package.py` によるレシピ駆動のバージョン管理と依存解決。
  - `rez-env` コマンドでの一時的なシェル環境生成。
  - Python API (`rez` パッケージ) を用いた自動化が可能。
  - Windows / macOS / Linux をサポートするが、Windows は追加依存（PowerShell、Visual Studio Build Tools 等）を要する場合がある。
- **導入時の注意**:
  - Windows では「Developer Mode」や `symlink` 許可が必要になるケースがある。
  - プロジェクト固有のパッケージレポジトリ（`packages_path`）を定義し、既存システムと衝突しないようにする。
  - 公式ドキュメントは更新頻度が高いため、`stable` ブランチだけでなく `latest` も確認して差分を把握すること。

## PySide6 (Qt for Python)
- **公式サイト**: <https://doc.qt.io/qtforpython/>
- **API リファレンス**: <https://doc.qt.io/qtforpython-6/>
- **概要**: Qt 6 系の公式 Python バインディング。Qt Widgets や Qt Quick を Python から利用できる。
- **主なモジュール**:
  - `PySide6.QtCore`, `PySide6.QtGui`, `PySide6.QtWidgets` などの Essentials。
  - `PySide6_Addons` に含まれる追加ウィジェット（Charts, DataVisualization など）。
  - `shiboken6` はバインディングの生成基盤として同梱される。
- **ライセンス**: LGPLv3 / 商用ライセンス。LGPL 遵守のため、ランタイム再配布時は動的リンクとライセンス告知が必要。
- **Windows Embeddable Package での注意**:
  - `python311.zip` には標準ライブラリが格納されるため、`Lib` ディレクトリの展開と `sitecustomize.py` 等の調整が必要。
  - Qt ランタイム DLL を同梱し、`qt.conf` でパスを設定すると安定する。
  - `pythonw.exe` で GUI を起動する際は、標準出力が見えないためログをファイルへ出力する仕組みを用意する。
- **開発時の留意点**:
  - Qt モジュールの初期化前に `QApplication` / `QGuiApplication` を適切に生成する。
  - Qt Designer 生成コードは `pyside6-uic` で Python へ変換できるが、バージョン差異を吸収するために手動調整が必要な場合がある。

## QtPy
- **公式ドキュメント**: <https://github.com/spyder-ide/qtpy>
- **概要**: PySide2/6 や PyQt5/6 を統一的に扱う薄い抽象化レイヤー。`QT_API` 環境変数を通じて実装を切り替える。
- **使用指針**:
  - プロジェクトでは `from qtpy import QtCore, QtGui, QtWidgets` の形式でインポートし、PySide6 直接依存を避ける。
  - `QtWidgets.QApplication.instance()` などのユーティリティは PySide6 でも動作するが、QtPy での挙動差を確認する。
  - 新しい Qt モジュール追加時は QtPy が対応済みか確認し、必要なら `QtPy` のバージョンアップを検討する。

## NodeGraphQt
- **公式ドキュメント**: <https://jchanvfx.github.io/NodeGraphQt/api/index.html>
- **GitHub**: <https://github.com/jchanvfx/NodeGraphQt>
- **概要**: Qt ベースのノードエディターフレームワーク。カスタムノード、ソケット、コンテキストメニューなどを備える。
- **注意事項**:
  - Qt 名前空間が `Qt` であることを前提とするため、`QtCore` 等を `Qt` に束縛する互換処理（例: `sotugyo.qt_compat.ensure_qt_module_alias()`）を行う。
  - バージョン 0.6 系は Qt6 対応が進行中であり、グラフィックビュー周りのバグ修正が頻繁。リリースノートを確認する。
  - パフォーマンス改善には `set_render_mode(NodeGraphQt.constants.RENDER_THREADED)` 等の API を検討する。

## OdenGraphQt
- **公式ドキュメント / README**: <https://github.com/odenthought/OdenGraphQt>
- **概要**: NodeGraphQt の派生で、より抽象的なデータ駆動ノードシステムを提供する。カスタムモデル・ビュー層を構築できるため、既存ノードとの互換性を評価すること。
- **運用時のポイント**:
  - NodeGraphQt に比べて更新頻度が低いため、PySide6 で動作させる際は issue tracker を確認する。
  - ライセンス（MIT）に基づき、改変箇所の記録と著作権表示を残す。

## packaging
- **公式ドキュメント**: <https://packaging.pypa.io/>
- **概要**: バージョン番号の解析 (`packaging.version`)、依存条件の評価 (`packaging.requirements`) などを提供。
- **利用例**:
  - NodeGraphQt や Rez のバージョン比較に使用可能。
  - PEP 440 準拠のバージョン指定を扱う。

## typing_extensions
- **公式ドキュメント**: <https://typing-extensions.readthedocs.io/>
- **概要**: Python 本体に取り込まれていない型ヒント機能を提供。`TypedDict`, `Literal`, `Protocol` など後方互換性を補完する。
- **留意点**:
  - Python 3.11 では多くの機能が標準化済みだが、`typing_extensions` 側の拡張が必要な場合がある。
  - 型チェッカー（Pyright, mypy）での挙動を確認し、バージョン差異を吸収する。

## ドキュメント更新フロー
1. 新しいモジュールを導入する場合、まず一次情報（公式ドキュメント / リポジトリ）を確認し、主要リンクと要点を本書へ追記する。
2. 参照元の URL は極力 HTTPS の公式ドメインを利用し、個人ブログなど信頼性の低い情報は補足扱いに留める。
3. バージョンアップ時は互換性リスク（破壊的変更、API 廃止）を洗い出し、`issue.md` に検証結果を記録する。
4. 重要な仕様差分が見つかった場合は `plan.md` に作業計画を記述した上で、`AGENT.md` に作業手順の追記を検討する。

## 調査チェックリスト
- [ ] 公式ドキュメントへのリンクと最終確認日を記載したか。
- [ ] 導入・配布時のライセンス条件を確認したか。
- [ ] Windows 環境固有の制約を洗い出したか。
- [ ] Qt バージョンと依存関係の整合性を確認したか。

## 更新履歴
- 2025-02-14: `src/sotugyo/ui/components/content_browser.py` のレイアウト間隔調整に伴い、UI 部品の設定値を確認した。
- 2025-12-19: `src/sotugyo/domain/projects` のパス正規化とレジストリ永続化の責務を整理し、`pathlib.Path` を前提とする設計方針を再確認した。
- 2025-12-19: Rez 実行ヘルパーと `ui/windows/views/node_editor.py` の Rez パッケージ管理ヘルパーを整理し、GUI と Rez ドメインの連携ポイントを再点検した。

最終更新日: 2025-12-19

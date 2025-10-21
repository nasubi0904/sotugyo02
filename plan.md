# ツール配布および開発計画

## 1. 目的
- **Python 3.11** と **PySide6** を用いて Maya 向けアセットツールを提供する。
- バイナリ凍結を避けつつ、ポータブルに配布可能な環境を整える。
- コンソールを表示しないシームレスなランチャーを用意し、非技術ユーザーでも簡単に起動できるようにする。

## 2. 配布戦略の概要
- **ランタイム**: 公式の **Windows 用 Python 3.11 Embeddable Package** を同梱する。
- **依存関係**: PySide6 などのサードパーティライブラリを `site-packages` ディレクトリに配置し、`_pth` から参照する。
- **アプリケーションコード**: 内製スクリプトは `zipapp` でまとめた `app.pyz` として提供する。
- **ランチャー**: `pythonw.exe` を用いて zipapp を実行し、ユーザーはショートカットやバッチをダブルクリックするだけで起動できるようにする。

## 3. ディレクトリ構成（ドラフト）
```
/ToolRoot
  /python/                <- Embeddable runtime（python.exe、pythonw.exe、python311.zip、python311._pth を配置）
  /site-packages/         <- PySide6 およびサードパーティライブラリを格納
  /app/
    app.pyz               <- zipapp 化したスタジオスクリプト
  start_tool.bat          <- Windows 用ランチャー（python\pythonw.exe app\app.pyz を呼び出す）
  start_tool.ps1          <- PowerShell 版ランチャー（任意）
  README.md               <- 利用者向けクイックスタートガイド
```

## 4. ランチャーの挙動
1. `start_tool.bat` は作業ディレクトリをツールルートに設定する。
2. 必要に応じて `PYTHONPATH` を設定し、zipapp から `site-packages` を参照できるようにする。
3. `python\pythonw.exe app\app.pyz` を実行する。
4. zipapp のブートストラップで `site-packages` やカスタム設定ディレクトリを `sys.path` に追加し、GUI エントリポイントを読み込む。

## 5. 開発ワークフロー
- 編集しやすいソースツリー（例: `src/`）で開発し、仮想環境を用いて迅速に検証する。
- ビルドスクリプト（例: `scripts/build_zipapp.py`）を用意し、以下を自動化する。
  1. ステージングフォルダの同期・クリーンアップ。
  2. ランタイムリソースのコピー。
  3. `python -m zipapp` を実行して `src` から `app/app.pyz` を生成。
  4. `python311._pth` に相対パスで `site-packages` などの検索パスを追記。
- バイナリランタイムなどの大容量ファイルはバージョン管理に含めず、構成手順とテンプレートのみを管理する。

## 6. 設定と拡張性
- キャッシュやログ、プロジェクトルートといった絶対パスは環境変数または `config/tool_settings.toml` のようなユーザー編集可能な設定から解決する。
- 既定では `%LOCALAPPDATA%/StudioTool/logs` にローテーションするログファイルを書き出し、`--debug` 指定時はコンソール出力も有効化する。
- `plugins/` ディレクトリを `sys.path` に追加してプラグインフックを提供する。

## 7. テストと品質保証
- 自動テストは開発用仮想環境上のソースツリーに対して実行する。
- クリーンな Windows VM 上で `start_tool.bat` をダブルクリックするスモークテストを実施し、zipapp が問題なく起動することを確認する。
- CI 上で `python311._pth` とパッケージ構成が同期しているかの検証を追加する。

## 8. 次のステップ
1. `sys.path` を調整する zipapp 内ブートストラップスクリプトの試作。
2. ビルドスクリプトのドラフト作成と、必要なアーティファクト（PySide6 の Wheel ファイル、ランタイム ZIP）のドキュメント化。
3. パッケージングの検証用に PySide6 の GUI スケルトン（アバウトダイアログ等）を作成。
4. インストール手順とトラブルシュートをまとめた利用者向け README を作成。

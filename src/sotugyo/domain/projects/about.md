# projects ジャンル概要

このディレクトリはプロジェクト管理ドメインの中核を構成し、以下の責務を持ちます。

- `registry.py` でプロジェクト一覧と最終選択状態を永続化する。
- `registry_service.py` でレジストリ操作（登録・削除・最終選択更新）を提供する。
- `settings.py` / `settings_service.py` でプロジェクト設定ファイルの読み書きを扱う。
- `structure.py` / `structure_service.py` で既定ディレクトリ構成の検証と生成を行う。
- `service.py` は上記サービスを束ねて UI 層へ提供するファサードとして機能する。

## 編集時の指針
- プロジェクトの永続化は `ProjectRegistry` を経由し、保存先ディレクトリの解決には `infrastructure.paths.get_app_config_dir()` を利用する。
- `ProjectRegistryService` / `ProjectSettingsService` / `ProjectStructureService` の公開 API を変更する際は、`ProjectService` を介した利用箇所を必ず確認する。
- プロジェクト構造の自動生成・検証ロジックは `structure_service.py` に集約し、UI や他ドメインで重複実装しない。

## 依存関係の考慮
- ファイルシステムにアクセスする処理は infrastructure 層へ委譲し、ここではビジネスルールに専念する。
- ユーザー設定ドメインとの連携は UI 層を経由して行い、直接依存を追加しない。

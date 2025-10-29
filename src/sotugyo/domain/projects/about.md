# projects ジャンル概要

このディレクトリはプロジェクト管理ドメインの中核を構成し、以下の責務を持ちます。

- `registry/` でプロジェクト一覧と最終選択状態の永続化・サービス化を行う。
- `settings/` でプロジェクト設定モデルと JSON リポジトリ、サービスを提供する。
- `structure/` で既定ディレクトリ構成のポリシー・検証ロジックを定義する。
- `service.py` は上記サービスを束ねて UI 層へ提供するファサードとして機能する。

## 編集時の指針
- プロジェクトの永続化は `ProjectRegistry` を経由し、保存先ディレクトリの解決には `infrastructure.paths.get_app_config_dir()` を利用する。
- `ProjectRegistryService` / `ProjectSettingsService` / `ProjectStructureService` の公開 API を変更する際は、`ProjectService` を介した利用箇所を必ず確認する。
- プロジェクト構造の自動生成・検証ロジックは `structure/` 以下に集約し、UI や他ドメインで重複実装しない。

## 依存関係の考慮
- ファイルシステムにアクセスする処理は infrastructure 層へ委譲し、ここではビジネスルールに専念する。
- ユーザー設定ドメインとの連携は UI 層を経由して行い、直接依存を追加しない。

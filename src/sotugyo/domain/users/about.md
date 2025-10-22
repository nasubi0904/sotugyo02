# users ジャンル概要

このディレクトリはユーザーアカウントの永続化と認証補助機能を提供します。

- `settings.py` に `UserSettingsManager` を定義し、Qt の `QSettings` を用いたユーザー情報の保存・取得を担当します。
- `hash_password()` および `UserAccount.verify_password()` でパスワードハッシュ処理を一元管理します。

## 編集時の指針
- パスワードの取り扱いは常に SHA-256 ハッシュ経由で行い、平文を保存しない。
- `QSettings` のグルーピングキー (`users`, `last_user_id` など) を変更する場合は移行手順を必ず検討する。
- UI 層からの利用を想定し、例外ではなく戻り値でエラー状況を表現する既存方針を維持する。

## 依存関係の考慮
- Qt 以外の永続化方式へ切り替える場合でも、`UserSettingsManager` の公開 API は互換性を保つ。
- ドメイン間でのユーザー参照は `UserSettingsManager` 経由で行い、他ドメインから直接 `QSettings` に触れない。

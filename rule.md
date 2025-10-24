# Python 設計・実装ルール

## 🎯 SOLID原則

💡 クラス設計の基本5原則。保守性・拡張性を高めるための指針。

### 単一責任原則（SRP）
→ 1つのクラスは1つの責任だけを持つ。変更理由は1つだけにする。

```python
# ✅ 1クラス1責任
class UserRepository:
    def save(self, user): pass

class EmailService:
    def send(self, to, message): pass

# ❌ 複数の責任
class User:
    def save_to_db(self): pass
    def send_email(self): pass
```

### 依存性逆転原則（DIP）
→ 具体的な実装ではなく、抽象（インターフェース）に依存させる。テストしやすくなる。

```python
# ✅ インターフェースに依存
class UserService:
    def __init__(self, repository: UserRepositoryInterface):
        self._repo = repository

# ❌ 具体クラスに依存
class UserService:
    def __init__(self):
        self._repo = MySQLUserRepository()
```

---

## 🏗️ クラス設計

💡 クラスは小さく、責任を明確に。変更に強い設計を目指す。

### 小さく保つ
→ 100行以内、メソッド10個以内が目安。大きくなったら分割する。

```python
# ✅ 100行以内、メソッド10個以内
class UserValidator:
    def validate_email(self): pass
    def validate_age(self): pass

# ❌ 神クラス（God Class）
class UserManager:  # 1000行、50メソッド
    ...
```

### 不変オブジェクト
→ 可能な限り状態を変更不可にする。バグが減り、並行処理も安全。

```python
# ✅ dataclass + frozen
from dataclasses import dataclass

@dataclass(frozen=True)
class Point:
    x: float
    y: float

# ❌ ミュータブル
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
```

### 継承より委譲
→ 「is-a」関係でないなら継承しない。組み合わせ（コンポジション）を使う。

```python
# ✅ コンポジション
class Car:
    def __init__(self):
        self.engine = Engine()
    
    def start(self):
        self.engine.start()

# ❌ 不適切な継承
class Car(Engine):
    pass
```

---

## 🔧 関数設計

💡 関数は短く、1つのことだけをする。読みやすさ＝保守性。

### 1関数1責任・短く
→ 20行以内が理想。1つの処理だけを行い、名前で意図を伝える。

```python
# ✅ 20行以内
def calculate_tax(amount, rate):
    return amount * rate

def apply_discount(amount, discount):
    return amount - discount

# ❌ 長い・複数責任
def process_order(order):
    # 100行: 検証、計算、保存、通知...
    ...
```

### 早期リターン
→ 異常系を先に処理して抜ける。ネストを減らし、正常系を読みやすく。

```python
# ✅ ガード節
def process_user(user):
    if not user:
        return None
    if not user.is_active:
        return None
    return user.process()

# ❌ ネストが深い
def process_user(user):
    if user:
        if user.is_active:
            return user.process()
    return None
```

### 副作用を避ける
→ 引数を変更しない、外部状態に依存しない。テストしやすく予測可能に。

```python
# ✅ 純粋関数
def calculate_total(items):
    return sum(item.price for item in items)

# ❌ 副作用あり
def calculate_total(items):
    total = 0
    for item in items:
        item.processed = True  # 副作用
        total += item.price
    return total
```

---

## 📦 モジュール設計

💡 責任ごとにレイヤーを分ける。依存の方向を一方向に保つ。

### レイヤー分離
→ ビジネスロジック・データアクセス・UIを分離。変更の影響を局所化。

```
project/
├── domain/          # ビジネスロジック
│   ├── models.py
│   └── services.py
├── infrastructure/  # データアクセス
│   └── repositories.py
└── presentation/    # UI/API
    └── views.py
```

### 循環依存を避ける
→ モジュール間の依存を一方向に。循環参照はリファクタリングのサイン。

```python
# ✅ 依存の方向を一方向に
# presentation → domain → infrastructure

# ❌ 循環依存
# module_a が module_b をインポート
# module_b が module_a をインポート
```

---

## 🚫 例外処理

💡 エラーは隠さず、適切に伝播させる。デバッグしやすいコードに。

### 具体的な例外
→ Exceptionは使わない。カスタム例外で意図を明確に。

```python
# ✅ カスタム例外
class ValidationError(Exception): pass

def validate(data):
    if not data:
        raise ValidationError("Data required")

# ❌ 汎用例外
def validate(data):
    if not data:
        raise Exception("Error")
```

### 例外を隠蔽しない
→ ログを残して再送出。握りつぶすと原因が追えなくなる。

```python
# ✅ ログ+再送出
try:
    process()
except DatabaseError as e:
    logger.error(f"DB error: {e}")
    raise

# ❌ 握りつぶし
try:
    process()
except Exception:
    pass
```

---

## 🎨 デザインパターン

💡 よくある問題には実証済みの解決パターンを使う。車輪の再発明を避ける。

### Factory
→ オブジェクト生成を一箇所に集約。生成ロジックの変更に強い。

```python
class UserFactory:
    @staticmethod
    def create(user_type):
        if user_type == "admin":
            return AdminUser()
        return RegularUser()
```

### Strategy
→ アルゴリズムを切り替え可能に。if/elseの連鎖を回避。

```python
class PaymentProcessor:
    def __init__(self, strategy):
        self._strategy = strategy
    
    def process(self, amount):
        return self._strategy.pay(amount)
```

### Dependency Injection
→ 依存をコンストラクタで注入。テスト時にモックに差し替え可能。

```python
# ✅ コンストラクタインジェクション
class OrderService:
    def __init__(self, repo, mailer):
        self._repo = repo
        self._mailer = mailer
```

---

## 🧪 テスト設計

💡 テストは仕様書。読みやすく、高速で、独立していること。

### AAA パターン
→ Arrange（準備）→ Act（実行）→ Assert（検証）の3段階で構造化。

```python
def test_calculate_tax():
    # Arrange
    amount = 1000
    rate = 0.1
    
    # Act
    result = calculate_tax(amount, rate)
    
    # Assert
    assert result == 100
```

### モック/スタブ
→ 外部依存（DB、API等）を偽物に置き換え。テストを高速・安定化。

```python
from unittest.mock import Mock

def test_user_service():
    # モックで外部依存を排除
    mock_repo = Mock()
    mock_repo.find.return_value = User("test")
    
    service = UserService(mock_repo)
    user = service.get_user(1)
    
    assert user.name == "test"
```

---

## ⚡ パフォーマンス

💡 まず動くコードを書く。遅かったら計測してから最適化。

### 遅延評価
→ 大量データはジェネレータで。必要な分だけメモリに載せる。

```python
# ✅ ジェネレータ
def process_large_data():
    for item in read_from_db():
        yield transform(item)

# ❌ 全件メモリ展開
def process_large_data():
    return [transform(item) for item in read_from_db()]
```

### キャッシング
→ 重い計算結果を保存。同じ入力なら再計算しない。

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_calculation(n):
    return complex_operation(n)
```

---

## 🔒 セキュリティ

💡 入力は信用しない。機密情報はコードに書かない。

### 入力検証
→ 全ての外部入力をバリデーション。SQLインジェクション等を防ぐ。

```python
# ✅ バリデーション
def create_user(email):
    if not validate_email(email):
        raise ValidationError("Invalid email")
    return User(email)
```

### 機密情報
→ パスワード、APIキー等は環境変数で管理。コミット厳禁。

```python
# ✅ 環境変数
import os
SECRET_KEY = os.getenv("SECRET_KEY")

# ❌ ハードコード
SECRET_KEY = "my-secret-123"
```

---

## 📝 設計チェックリスト

### クラス
- [ ] 100行以内
- [ ] 単一責任
- [ ] 依存注入可能
- [ ] 不変性を優先

### 関数
- [ ] 20行以内
- [ ] 1つの処理のみ
- [ ] 副作用なし
- [ ] 早期リターン

### モジュール
- [ ] レイヤー分離
- [ ] 循環依存なし
- [ ] 明確な責任

### テスト
- [ ] 全機能カバー
- [ ] 高速実行
- [ ] 独立性
- [ ] モック活用

---
name: enable-credit-deduction
overview: 将 enable_credit 设为 True，使 Copilot 发送消息时正确扣减用户积分
todos:
  - id: enable-credit-setting
    content: 将 `settings.py` 中 `enable_credit` 默认值从 `False` 改为 `True`，并在 `.env.default` 中添加 `ENABLE_CREDIT=true`
    status: completed
  - id: seed-initial-credits
    content: 在 `user.py` 的 `get_or_create_user()` 中为新创建用户授予 500 初始积分（懒加载导入 UserCredit，使用 idempotent key 防重复）
    status: completed
    dependencies:
      - enable-credit-setting
---

## 用户需求

Copilot 对话发送消息时不减少 credit。需要启用积分系统，使每次 Copilot LLM 调用正常扣减积分。同时要求新初始用户拥有 5 积分（$5.00 = 500 分）。

## 核心功能

1. **启用积分扣减**：将 `enable_credit` 默认值改为 `True`，使 Copilot 消息成本通过 `spend_copilot_credits` → `UserCredit.spend_credits` 正常写入数据库扣减
2. **新用户初始积分**：新用户注册时自动授予 500 积分（$5.00），使用 idempotent key 防止重复发放
3. **环境变量配置**：在 `.env.default` 中添加 `ENABLE_CREDIT=true` 条目

## 技术栈

- 后端：Python (FastAPI) + Prisma ORM + PostgreSQL
- 配置管理：Pydantic Settings（读取 `.env` 文件）

## 实现方案

### 1. 启用积分系统（settings.py）

将 `enable_credit` 的 `default` 从 `False` 改为 `True`。Pydantic Settings 的 `SettingsConfigDict(env_file=".env")` 会自动读取 `.env` 中的 `ENABLE_CREDIT` 环境变量，默认值与 `.env` 文件配合使用。

修改位置：`backend/util/settings.py` 第 138-141 行

### 2. 环境变量配置（.env.default）

添加 `ENABLE_CREDIT=true` 条目，供部署时覆盖默认值。

修改位置：`autogpt_platform/.env.default`

### 3. 新用户初始积分授予（user.py）

在 `get_or_create_user()` 中，当 Prisma 检测到用户不存在并创建新用户后，通过懒加载导入 `credit` 模块的 `UserCredit`，调用 `grant_credits()` 写入 500 积分的 GRANT 交易。

关键设计决策：

- **懒加载导入**：`user.py` 是底层模块，`credit.py` 依赖 `user.py`，如果在 `user.py` 顶部导入 `credit` 会造成循环依赖。因此使用 `get_or_create_user` 内部 `import` 的方式
- **Idempotent key**：使用 `INITIAL_GRANT-{user_id}` 作为 transaction_key，利用 `UserCredit._add_transaction` 内部的 `UniqueViolationError` 处理（Prisma upsert），确保同一用户不会重复收到初始积分
- **静默失败**：初始积分授予失败不应阻止用户注册流程

### 数据流

```
用户注册
  → get_or_create_user()
    → prisma.user.create() 创建用户记录
    → UserCredit.grant_credits(user_id, 500, "Initial sign-up grant")
      → _add_transaction(amount=500, type=GRANT, transaction_key="INITIAL_GRANT-{user_id}")
        → 写入 CreditTransaction 行 + 更新 UserBalance

用户发送 Copilot 消息
  → spend_copilot_credits()
    → get_user_credit_model(user_id) → UserCredit()  (因为 enable_credit=True)
    → UserCredit.spend_credits(cost, metadata)
      → _add_transaction(amount=-cost, type=USAGE)
        → 从 UserBalance 扣减积分
```
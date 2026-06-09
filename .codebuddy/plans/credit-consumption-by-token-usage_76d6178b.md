---
name: credit-consumption-by-token-usage
overview: 在 copilot 聊天对话完成后，根据 LLM 调用消耗的 token 量按比例自动扣除用户 credits，填补当前只追踪 token 但不扣费的缺口。
todos:
  - id: add-credits-per-usd
    content: 在 settings.py 新增 CREDITS_PER_USD 配置项，默认值 1000
    status: completed
  - id: add-spend-helper
    content: 在 token_tracking.py 新增 spend_copilot_credits 集中扣费函数，封装 USD→credits 换算、spend_credits 调用、异常日志
    status: completed
    dependencies:
      - add-credits-per-usd
  - id: charge-baseline
    content: 在 baseline/service.py 的 persist_and_record_usage 调用后添加 spend_copilot_credits 扣费
    status: completed
    dependencies:
      - add-spend-helper
  - id: charge-sdk-sync
    content: 在 sdk/service.py 同步路径的 persist_and_record_usage 调用后添加 spend_copilot_credits 扣费
    status: completed
    dependencies:
      - add-spend-helper
  - id: charge-sdk-reconcile
    content: 在 sdk/openrouter_cost.py 异步对账路径的 persist_and_record_usage 调用后添加 spend_copilot_credits 扣费
    status: completed
    dependencies:
      - add-spend-helper
  - id: charge-title
    content: 在 service.py 标题生成的 persist_and_record_usage 调用后添加 spend_copilot_credits 扣费
    status: completed
    dependencies:
      - add-spend-helper
---

## 用户需求

目前用户对话不消耗 credit，需要让 credit 根据调用大模型使用的 token 量按比例自动消耗。

## 产品概述

在每次聊天对话的 LLM 调用完成后，自动从用户信用余额中扣减相应 credits。扣费额度基于 LLM 提供商报告的实际 USD 成本，按固定汇率换算为 credits。

## 核心功能

- **Token 用量换算**：将 LLM 调用的实际 USD 成本（cost_usd）乘以配置的 CREDITS_PER_USD 汇率，得到应扣 credits 数量
- **自动扣费**：在每次对话 LLM 调用完成后（persist_and_record_usage 之后），自动调用 spend_credits 扣减用户余额
- **全路径覆盖**：Baseline 路径、SDK 同步路径、SDK 异步对账路径、标题生成路径均触发扣费
- **graceful 错误处理**：扣费失败仅记录日志，不中断聊天流（参考现有 _charge_block_credits 模式）
- **启用/禁用开关**：受 enable_credit 配置控制，禁用时自动跳过扣费

## 技术栈

- 后端：Python + FastAPI + Prisma
- 信用系统：Prisma UserBalance + CreditTransaction 表
- LLM 调用：OpenAI-compatible / Anthropic SDK / OpenRouter

## 实现方案

### 核心策略

在 `token_tracking.py` 新增集中扣费函数 `spend_copilot_credits`，封装 USD→credits 换算 + spend_credits 调用。在 4 个 persist_and_record_usage 调用点之后立即调用该函数。

### 换算公式

```
credits_to_charge = max(1, int(cost_usd * CREDITS_PER_USD))
```

- `CREDITS_PER_USD` 默认值 1000（1 USD = 1000 credits），可在配置中调整
- cost_usd 为 None 或 ≤ 0 时跳过扣费

### 调用点与路径互斥关系

```
Baseline 路径 (DeepSeek/OpenRouter)
  └── baseline/service.py finally 块 → 扣费

SDK 路径 (Claude Agent)
  ├── reconcile 启用 → openrouter_cost.py 异步对账 → 扣费（真实 cost）
  └── reconcile 禁用 → sdk/service.py 同步路径 → 扣费（估算 cost）
       （两条路径互斥，不会重复扣费）

标题生成
  └── service.py _record_title_cost → 扣费
```

### 错误处理

参考 `copilot/tools/helpers.py` 的 `_charge_block_credits` 模式：扣费成功正常返回，失败时记录 BILLING_LEAK 日志，区分 INSUFFICIENT_BALANCE 和 UNEXPECTED_ERROR，不向上层抛异常。

### 架构扩展性

- 集中扣费函数便于未来调整汇率、增加审计日志、添加多模型差异化定价
- 与现有 enable_credit 开关完全兼容（DisabledUserCredit 的 spend_credits 为 no-op）

## 实现细节

### 修改文件清单

```
autogpt_platform/backend/backend/
├── util/
│   └── settings.py                          # [MODIFY] 新增 CREDITS_PER_USD 配置项
├── copilot/
│   ├── token_tracking.py                    # [MODIFY] 新增 spend_copilot_credits 集中扣费函数
│   ├── baseline/
│   │   └── service.py                       # [MODIFY] 在 persist_and_record_usage 后调用扣费
│   ├── sdk/
│   │   ├── service.py                       # [MODIFY] 同步路径在 persist_and_record_usage 后调用扣费
│   │   └── openrouter_cost.py               # [MODIFY] 异步对账路径在 persist_and_record_usage 后调用扣费
│   └── service.py                           # [MODIFY] 标题生成在 persist_and_record_usage 后调用扣费
```

### 关键代码结构

**settings.py 新增配置：**

```
credits_per_usd: int = Field(default=1000, description="...")
```

**token_tracking.py 新增函数签名：**

```python
async def spend_copilot_credits(
    *,
    user_id: str | None,
    cost_usd: float | None,
    reason: str = "copilot_chat_turn",
    model: str | None = None,
    log_prefix: str = "",
) -> None:
```

**各调用点模式（4个文件一致）：**

```python
await persist_and_record_usage(...)
await spend_copilot_credits(
    user_id=user_id,
    cost_usd=<匹配 persist 的 cost_usd>,
    reason="copilot_chat_turn",  # 或 "copilot_title_generation"
    model=<model>,
    log_prefix=<prefix>,
)
```
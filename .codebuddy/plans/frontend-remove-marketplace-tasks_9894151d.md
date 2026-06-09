---
name: frontend-remove-marketplace-tasks
overview: 从前端移除两个市场相关的引导任务（MARKETPLACE_ADD_AGENT 和 MARKETPLACE_RUN_AGENT），更新 Wallet 任务界面、usage limit 可视化和 credit 计数。
todos:
  - id: update-wallet-tasks
    content: 移除 Wallet.tsx 中 "First Wins" 任务组的 MARKETPLACE_ADD_AGENT 和 MARKETPLACE_RUN_AGENT 两个任务条目
    status: completed
  - id: update-types
    content: 将 types.ts 中 MARKETPLACE_ADD_AGENT 和 MARKETPLACE_RUN_AGENT 从 "First Wins" 区域移至 "No longer used but tracked" 区域
    status: completed
---

## 用户需求

前端界面尚未同步后端变更，需要更新前端以反映移除两个市场相关引导任务后的可视化变动。

## 核心变更

- 从 Wallet 钱包组件的 "First Wins" 任务组中移除 `MARKETPLACE_ADD_AGENT` 和 `MARKETPLACE_RUN_AGENT` 两个任务
- 更新 TypeScript 类型定义，将这两个步骤标记为 "No longer used but tracked"
- 任务总数从 8 降为 6，"First Wins" 组奖励从 $5 降为 $3，总可获取奖励从 $12 降为 $10
- 已完成/总任务计数由组件自动重新计算
- Credit 余额由后端 API 返回，前端无需额外修改

## 后端已完成的对应修改

- `data/onboarding.py`：已删除 `_reward_user` 中的两个市场任务奖励分支
- `api/features/v1.py`：已删除 `MARKETPLACE_RUN_AGENT` 触发调用
- `api/features/library/routes/agents.py`：已删除 `MARKETPLACE_ADD_AGENT` 触发调用及 import

## 技术方案

### 修改文件清单

仅修改两个前端文件，均为精确删除/移动类型定义：

| 文件 | 操作 | 说明 |
| --- | --- | --- |
| `frontend/src/components/layout/Navbar/components/Wallet/Wallet.tsx` | 删除行 62-76 | 移除两个市场任务对象 |
| `frontend/src/lib/autogpt-server-api/types.ts` | 移动行 878-879 | 将枚举值从 "First Wins" 移到 "No longer used" |


### 不改动的文件

- `WalletTaskGroups.tsx`：纯展示组件，通过 props 接收任务列表，无需修改
- `openapi.json`：后端 Prisma 枚举值仍存在，自动生成文件不受影响
- `onboardingStep.ts`：同上，自动生成文件不受影响

### 影响范围

- 任务数量计算（`totalCount`、`completedCount`）由 `groups.reduce()` 自动重新计算
- 奖励金额由 `group.tasks.reduce()` 自动重新计算
- Credit 余额通过 `useCredits()` 钩子从后端 API 获取，不受影响
- WebSocket 通知中的 confetti 动画仍正常工作（`taskIds.includes()` 过滤）
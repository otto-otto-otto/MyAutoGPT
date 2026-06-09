---
name: remove-agent-marketplace-build-copilot
overview: 从 AutoGPT 前端和后端移除 Agent 库、Marketplace、Build 构建器和 CoPilot 功能模块，精简项目至纯 REST API + 基础聊天界面。
todos:
  - id: remove-backend-copilot-code
    content: 修改后端 app.py 移除 CoPilot 导入和进程启动；修改 rest_api.py 移除 UserPaywalledError 异常处理和 /api/copilot 路由；删除 backend/copilot/ 整个目录
    status: pending
  - id: update-pyproject-and-compose
    content: 修改 pyproject.toml 移除 copilot-executor 和 copilot-bot 脚本；修改 docker-compose.platform.yml 移除 copilot_executor 服务定义
    status: pending
    dependencies:
      - remove-backend-copilot-code
  - id: update-navbar
    content: 修改 Navbar/helpers.tsx 清空 loggedInLinks/loggedOutLinks 并移除 creator dashboard 菜单；修改 Navbar/Navbar.tsx 简化 actualLoggedInLinks 为单一 Library 入口并精简移动端图标映射
    status: pending
  - id: delete-frontend-pages
    content: "删除 frontend 页面目录: marketplace/、build/、copilot/、library/agents/"
    status: pending
  - id: delete-agent-components
    content: "删除 agent 相关组件: EditAgentModal/、PublishAgentModal.tsx、RunAgentInputs.tsx、AgentImageItem.tsx、AgentImages.tsx、FeaturedAgentCard.tsx、AgentsSection.tsx、AgentActivityDropdown/"
    status: pending
  - id: cleanup-references
    content: "清理残留的 import 引用: FeaturedSection.tsx、BecomeACreator.tsx 等文件；简化 library/page.tsx 移除 Agent 相关导入"
    status: pending
    dependencies:
      - delete-frontend-pages
      - delete-agent-components
  - id: verify-build
    content: 验证前端编译无报错（检查 TypeScript 和 ESLint）；确认后端 app.py 导入正常
    status: pending
    dependencies:
      - cleanup-references
---

## 用户需求

从 AutoGPT 项目中移除 Agent（UI 层）、Marketplace、Build 页面及 CoPilot 功能模块。

## 产品概述

精简后的项目保留核心 REST API、WebSocket 通信、Execution Manager、Scheduler 等基础架构服务，移除面向用户的 Agent 库浏览、市场展示、构建器和 AI 助手聊天页面。

## 核心调整

- **导航栏简化**：移除 Marketplace、Build、Copilot/Home 入口，仅保留核心功能入口
- **页面清理**：删除 marketplace、build、copilot、library/agents 等目录及其组件
- **后端精简**：移除 Copilot 后端服务、限流路由、相关异常处理器
- **Docker 服务**：移除 copilot_executor 容器
- **保持运行**：保留 REST API (8006)、WebSocket (8001)、Executor (8002)、Scheduler (8003) 等核心容器

## 技术栈

- 后端：Python 3.13 + FastAPI + Uvicorn + Poetry 包管理
- 前端：Next.js 15 + TypeScript + Tailwind CSS（Docker 容器运行）
- 基础设施：PostgreSQL、Redis、RabbitMQ、Supabase

## 实现方案

### 后端修改（4 处文件修改 + 1 个目录删除）

1. **`backend/app.py`**：第 41-42 行移除 `CoPilotChatBridge` 和 `CoPilotExecutor` 导入；第 56-57 行从 `run_processes()` 调用中移除这两个进程
2. **`backend/api/rest_api.py`**：第 57 行移除 `UserPaywalledError` 导入；第 316-318 行移除异常处理器；第 359-363 行移除 `/api/copilot` 前缀的限流管理路由
3. **`backend/copilot/`**：删除整个目录
4. **`pyproject.toml`**：第 140-141 行移除 `copilot-executor` 和 `copilot-bot` 脚本入口
5. **`docker-compose.platform.yml`**：第 252-288 行移除 `copilot_executor` 服务定义

### 前端修改（导航栏核心 + 目录删除 + 引用清理）

**导航栏改造**：

- `components/layout/Navbar/helpers.tsx`：`loggedInLinks` 和 `loggedOutLinks` 数组清空；移除 Creator Dashboard 和 Publish agent 菜单项
- `components/layout/Navbar/Navbar.tsx`：`actualLoggedInLinks` 从 `[{name:"Home",href:"/copilot"},{name:"Agents",href:"/library"},...loggedInLinks]` 改为仅保留单一入口 `[{name: "Library", href: "/library"}]`；移动端图标映射简化

**整目录删除（4 个页面目录 + 2 个组件目录）**：

- `src/app/(platform)/marketplace/` (80+ 文件)
- `src/app/(platform)/build/` 
- `src/app/(platform)/copilot/`
- `src/app/(platform)/library/agents/` (115 文件)
- `components/contextual/EditAgentModal/`
- `components/layout/Navbar/components/AgentActivityDropdown/`

**单个文件删除（6 个）**：

- `components/contextual/PublishAgentModal/PublishAgentModal.tsx`
- `components/contextual/RunAgentInputs/RunAgentInputs.tsx`
- `components/__legacy__/AgentImageItem.tsx`
- `components/__legacy__/AgentImages.tsx`
- `components/__legacy__/FeaturedAgentCard.tsx`
- `components/__legacy__/composite/AgentsSection.tsx`

**引用清理**：

- `components/__legacy__/composite/FeaturedSection.tsx`：移除对 `AgentImages`、`FeaturedAgentCard`、`AgentsSection` 的 import
- `components/__legacy__/BecomeACreator.tsx`：移除对 `PublishAgentModal` 的 import
- `app/(platform)/library/page.tsx`：简化页面，移除 `LibraryAgentList`、`useLibraryAgents` 等 Agent 相关导入，替换为简单的占位页面
- 其他 17 个文件中的 import 引用（因关联页面目录整体删除，大部分引用自然失效，需逐一确认清理）

### 注意事项

- 保留 `backend/blocks/agent.py` 作为核心系统依赖（被 executor、graph、orchestrator 使用）
- 保留 `backend/api/features/library/` 目录（作为核心 API 基础设施）
- library 页面的 skills 和 followups 子目录保留
- 已修改的文件（`_anti_bot.py`、`.env`、`docker-compose.platform.yml`）不需回滚
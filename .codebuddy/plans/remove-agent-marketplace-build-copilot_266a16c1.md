---
name: remove-agent-marketplace-build-copilot
overview: 移除前端 Agent/Marketplace/Build 页面，并移除 CoPilot 模块中全部 Agent 相关知识（Agent CRUD、搜索、执行、生成器等工具），保留 CoPilot 核心聊天和基础设施。
todos:
  - id: delete-agent-tool-files
    content: 删除 12 个 Agent 工具文件及对应测试（create_agent、edit_agent、customize_agent、run_agent、find_agent、find_library_agent、agent_search、agent_output、validate_agent、fix_agent、get_agent_building_guide、list_agent_triggers）和 agent_generator/ 目录
    status: completed
  - id: update-tool-registry
    content: 修改 tools/__init__.py 移除 Agent 工具导入和 TOOL_REGISTRY 注册项；修改 tools/models.py 移除 Agent 相关 ResponseType 枚举值和 Pydantic 模型
    status: completed
    dependencies:
      - delete-agent-tool-files
  - id: update-permissions
    content: 修改 permissions.py 从 ALL_TOOLS 中移除 12 个 Agent 工具名
    status: completed
    dependencies:
      - delete-agent-tool-files
  - id: delete-sdk-guide
    content: 删除 sdk/agent_generation_guide.md
    status: completed
  - id: delete-frontend-pages
    content: 删除前端页面目录 marketplace/、build/、library/agents/
    status: completed
  - id: delete-agent-components
    content: 删除 Agent 相关组件：EditAgentModal、PublishAgentModal、RunAgentInputs、AgentImage、FeaturedAgentCard、AgentsSection、AgentActivityDropdown
    status: completed
  - id: update-navbar
    content: 修改 Navbar/helpers.tsx 清空 Marketplace/Build 链接；修改 Navbar/Navbar.tsx 简化导航为仅保留 Library 入口
    status: completed
    dependencies:
      - delete-frontend-pages
      - delete-agent-components
  - id: cleanup-remaining-refs
    content: 清理 baseline/service.py、library/page.tsx 等文件中残留的 Agent 引用；删除 becomeACreator 等失效引用
    status: completed
    dependencies:
      - update-tool-registry
      - update-navbar
  - id: verify-backend-import
    content: 验证后端 poetry run python -c "from backend.copilot.tools import TOOL_REGISTRY" 导入正常且不含 Agent 工具
    status: completed
    dependencies:
      - cleanup-remaining-refs
---

## 用户需求

保留 CoPilot 聊天助手、bot、executor、baseline、SDK 等核心功能，但移除其对 Agent 的所有知识。同时移除前端 Agent 库页面、Marketplace 页面和 Build 构建器页面。

## 产品概述

精简后的 CoPilot 不再具备创建、编辑、定制、运行、搜索、验证、修复 Agent 的能力。前端仅保留基础库入口。后端核心 infrastructure（executor、graph、orchestrator 等）不受影响。

## 核心改造范围

### 后端 CoPilot - 移除 Agent 知识

- 删除 12 个 Agent 工具及其对应测试文件
- 删除整个 agent_generator 子系统（7个文件）
- 删除 SDK agent_generation_guide.md
- 修改 tools/**init**.py 工具注册表
- 修改 permissions.py 权限列表
- 修改 tools/models.py 移除 Agent 相关模型和枚举

### 前端 - 移除 Agent/Marketplace/Build 页面

- 删除 marketplace/、build/、library/agents/ 三个页面目录
- 删除 Agent 相关组件（EditAgentModal、PublishAgentModal 等）
- 修改导航栏，移除 Marketplace/Build/Copilot/Agents 入口

## 技术栈

- 后端：Python 3.13 + FastAPI + Poetry
- 前端：Next.js 15 + TypeScript（Docker 容器运行）
- 基础设施：PostgreSQL、Redis、RabbitMQ、Supabase

## 实现方案

### 后端 CoPilot 修改策略

采用"精确删除 + 注册表更新"策略，确保不影响 CoPilot 核心功能的同时彻底清除 Agent 知识。

### 前端修改策略

整体删除页面目录后，清理导航栏引用。导航改为仅保留 Library 入口。

## 实现细节

### 第一组：删除 CoPilot Agent 工具文件

从 `backend/backend/copilot/tools/` 删除以下文件：

| 文件 | 关联测试 |
| --- | --- |
| create_agent.py | create_agent_test.py |
| edit_agent.py | edit_agent_test.py |
| customize_agent.py | customize_agent_test.py |
| run_agent.py | run_agent_test.py |
| find_agent.py | - |
| find_library_agent.py | find_library_agent_test.py |
| agent_search.py | agent_search_test.py |
| agent_output.py | - |
| validate_agent.py | validate_agent_test.py |
| fix_agent.py | fix_agent_test.py |
| get_agent_building_guide.py | get_agent_building_guide_test.py |
| list_agent_triggers.py | - |
| agent_guide_gate_test.py | - |
| agent_generator/（整个目录） | 含 validator_test.py, fixer_test.py |


### 第二组：修改工具注册表 tools/**init**.py

- 移除 import：create_agent, customize_agent, edit_agent, find_agent, find_library_agent, fix_agent, validate_agent, get_agent_building_guide, agent_output, list_agent_triggers, run_agent
- 从 TOOL_REGISTRY 移除对应条目
- 移除 find_agent_tool 和 run_agent_tool 向后兼容变量

### 第三组：修改权限列表 permissions.py

从 ALL_TOOLS 中移除：create_agent, customize_agent, edit_agent, find_agent, find_library_agent, fix_agent_graph, get_agent_building_guide, list_agent_triggers, move_agents_to_folder, run_agent, validate_agent_graph, view_agent_output

### 第四组：修改 models.py

从 ResponseType 枚举移除 Agent 相关值（第21-37行 AGENTS_FOUND 到 AGENT_BUILDER_FIX_RESULT），从文件末尾移除 Agent 相关 Pydantic 模型

### 第五组：删除 SDK 指南

删除 `sdk/agent_generation_guide.md`

### 第六组：删除前端页面和组件

- 删除 `src/app/(platform)/marketplace/`
- 删除 `src/app/(platform)/build/`
- 删除 `src/app/(platform)/library/agents/`
- 删除 Agent 相关 UI 组件

### 第七组：修改导航栏

- helpers.tsx：清空 loggedInLinks 和 loggedOutLinks
- Navbar.tsx：actualLoggedInLinks 仅保留 Library 入口

## 架构影响

```
修改前: CoPilot ←→ Agent工具 + Agent生成器 + 市场集成
修改后: CoPilot ←→ 仅保留 Block执行 + 内存 + 文件 + Web + 技能 工具
```

## 目录结构

```
backend/backend/copilot/
├── tools/
│   ├── __init__.py              # [MODIFY] 移除 Agent 工具导入和注册
│   ├── models.py                # [MODIFY] 移除 Agent 相关类型
│   ├── [agent工具文件]          # [DELETE] 12个工具 + 测试
│   └── agent_generator/         # [DELETE] 整个目录
├── permissions.py               # [MODIFY] 移除 Agent 工具权限
└── sdk/
    └── agent_generation_guide.md # [DELETE]

frontend/src/
├── app/(platform)/
│   ├── marketplace/             # [DELETE] 整个目录
│   ├── build/                   # [DELETE] 整个目录
│   └── library/agents/          # [DELETE] 整个目录
└── components/layout/Navbar/
    ├── helpers.tsx               # [MODIFY] 清空导航链接
    └── Navbar.tsx                # [MODIFY] 简化导航入口
```
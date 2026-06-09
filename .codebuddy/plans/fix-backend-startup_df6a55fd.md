---
name: fix-backend-startup
overview: 启动 AutoGPT 后端 REST API 服务（端口 8006），修复前端无法连接后端的问题。
todos:
  - id: start-backend
    content: 在 backend 目录执行 `poetry run app` 启动后端 REST API 及所有微服务
    status: completed
  - id: verify-backend-port
    content: 验证 8006 端口已进入 LISTENING 状态，确认后端服务正常启动
    status: completed
    dependencies:
      - start-backend
  - id: verify-health
    content: 调用 /health 端点验证后端数据库连接正常，返回 {"status":"healthy"}
    status: completed
    dependencies:
      - verify-backend-port
  - id: verify-frontend-proxy
    content: 通过前端代理 `/api/proxy/api/health` 验证前端到后端链路通畅
    status: completed
    dependencies:
      - verify-health
---

## 用户需求

修复 AutoGPT 前端无法连接后端的问题。经过前期诊断，确认根本原因是后端 REST API 服务（端口 8006）未启动。

## 前置条件（已确认）

- 前端 Next.js 运行在 localhost:3000 ✅
- PostgreSQL (5432)、RabbitMQ (5672)、Supabase/Kong (8000)、Redis (17000) 等依赖服务均正常运行 ✅
- `ddgs` 依赖缺失已修复，`app.py` 导入测试通过 ✅
- 后端 .env 环境变量已配置完整（DeepSeek API、数据库、Supabase 认证等）✅

## 需要完成的任务

1. 启动后端 REST API 服务（`poetry run app`），使其监听 8006 端口
2. 验证后端 /health 端点响应正常
3. 验证前端代理 `/api/proxy/api/*` 能正确转发请求到后端
4. 如有额外依赖缺失或配置问题，一并修复

## 技术栈

- 后端：Python FastAPI + Uvicorn，包管理 Poetry
- 前端：Next.js 15.5 + TypeScript
- 数据库：PostgreSQL + Prisma ORM
- 中间件：Redis、RabbitMQ、Supabase Auth

## 实现方案

### 启动策略

使用 `poetry run app` 在 `d:\cn gpt\AutoGPT-master\autogpt_platform\backend\` 目录下启动后端全部微服务。`app.py `的 `main()` 函数通过 `run_processes()` 依次启动所有子进程（DatabaseManager、Scheduler、NotificationManager、PlatformLinkingManager、WebsocketServer、AgentServer、ExecutionManager、CoPilotChatBridge、CoPilotExecutor），其中 REST API（AgentServer）运行在 8006 端口。

### 验证策略

1. 启动后检查 8006 端口是否进入 LISTENING 状态
2. 调用 `http://localhost:8006/health` 确认后端健康
3. 通过前端代理 `/api/proxy/api/health` 确认前端到后端的链路通畅

### 性能与可靠性

- 后端启动使用 `run_processes` 管理多进程生命周期，最后启动的 `CoPilotExecutor` 在前台运行，其他进程在后台
- `/health` 端点会检查数据库连接状态，可作为综合健康检查
- 前端代理 `route.ts` 已实现完善的错误处理，返回 502 状态码表示后端不可达
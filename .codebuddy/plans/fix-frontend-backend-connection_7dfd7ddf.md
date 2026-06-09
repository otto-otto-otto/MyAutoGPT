---
name: fix-frontend-backend-connection
overview: 诊断并修复前端无法连接后端的问题，包括检查缺失文件、服务配置、代理路由、环境变量等。
todos:
  - id: fix-frontend-env
    content: 统一前端 .env 和 .env.default 中的后端地址，将 AGPT_SERVER_URL 从 127.0.0.1 改为 localhost
    status: completed
  - id: verify-backend-env
    content: 检查并修正后端 .env 中的数据库连接配置，确保与 Docker 或本地基础设施服务一致
    status: completed
  - id: start-docker-infra
    content: 提供 Docker Compose 启动后端依赖服务（PostgreSQL、Redis、RabbitMQ、Supabase）的指南和验证步骤
    status: completed
    dependencies:
      - verify-backend-env
  - id: verify-connection
    content: 验证前端到后端的完整连接链路：浏览器 → /api/proxy → 后端 8006 端口 API 响应正常
    status: completed
    dependencies:
      - fix-frontend-env
      - start-docker-infra
---

## 用户需求

用户报告"前端无法连接后端，有部分文件缺失问题"。

## 问题诊断结论

经过对项目代码库的全面探索，**所有源代码文件均存在且结构完整**，包括：

- 前端代理路由 `api/proxy/[...path]/route.ts`（完整可用）
- 后端 `platform_linking/` 目录及所有模块（完整可用）
- `copilot/tools/` 下所有工具文件（完整可用）
- 所有 `__init__.py` 导入链（完整可用）

**真正的根源问题是后端基础设施服务（PostgreSQL、Redis Cluster、RabbitMQ、Supabase）未启动，导致后端无法完成初始化。**

## 需要修复的具体问题

1. **后端 .env 配置**：数据库密码为占位符 `your-super-secret-and-long-postgres-password`，与 Docker 基础设施的默认密码一致，但本地直接启动时可能不匹配
2. **前端 .env 配置**：API 地址使用 `127.0.0.1`、WS 地址使用 `localhost`，建议统一为 `localhost` 以避免潜在 cookie/认证域问题
3. **缺少启动引导说明**：项目需要 9 个后端服务进程同时运行，依赖 Docker Compose 启动的基础设施，用户需要清晰的启动流程指导

## 技术方案

### 配置修复策略

#### 1. 前端环境变量统一化

将前端 `.env` 和 `.env.default` 中的后端地址统一使用 `localhost`（而非混用 `127.0.0.1`），确保 cookie、CORS 和认证域的配置一致性。

**变更内容**：

- `NEXT_PUBLIC_AGPT_SERVER_URL`：从 `http://127.0.0.1:8006/api` 修正为 `http://localhost:8006/api`
- `NEXT_PUBLIC_AGPT_WS_SERVER_URL`：保持 `ws://localhost:8001/ws` 不变
- `NEXT_PUBLIC_SUPABASE_URL`：保持 `http://localhost:8000` 不变

#### 2. 后端 CORS 配置确认

后端 `settings.py` 中 `backend_cors_allow_origins` 默认值为 `["http://localhost:3000"]`，与前端运行在 `localhost:3000` 匹配。由于前端客户端请求通过 Next.js 服务端代理（`/api/proxy/`）转发，不涉及浏览器 CORS，此配置仅在 WS 连接时作用，当前配置充分。

#### 3. 后端基础设施启动方案

项目提供 Docker Compose 方案启动所有依赖服务。核心启动命令：

```
cd autogpt_platform
docker compose -f docker-compose.yml -f docker-compose.platform.yml up -d
```

后端 FastAPI 需要一个可运行的 `.env` 文件，确保数据库、Redis、RabbitMQ 等配置与 Docker 服务匹配。

### 实现要点

- **不引入新架构模式**：所有修改都在现有 `.env` 文件中进行，零代码改动
- **最小化变更范围**：仅修改前端 2 个 .env 文件和必要时后端 .env 配置说明
- **保持向后兼容**：`localhost` 和 `127.0.0.1` 在本地开发中等效，但 `localhost` 避免 cookie 域匹配问题
- **参考现有模式**：前端 `helpers.ts` 中 `buildServerUrl` 通过环境变量获取后端地址，配置修改后自动生效；后端 `settings.py` 中 CORS 默认值无需改动

### 核心目录结构

```
autogpt_platform/
├── frontend/
│   ├── .env                          # [MODIFY] 统一 API 地址为 localhost
│   └── .env.default                  # [MODIFY] 统一 API 地址为 localhost
├── backend/
│   └── .env                          # [MODIFY] 确保数据库/Redis/RabbitMQ 配置正确
└── docker-compose.platform.yml       # [参考] Docker 服务启动配置
```
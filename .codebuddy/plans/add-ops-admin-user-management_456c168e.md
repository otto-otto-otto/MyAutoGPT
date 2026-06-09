---
name: add-ops-admin-user-management
overview: 为 AutoGPT 项目添加运维端用户管理界面，支持查看所有用户的用户名、credit 余额和消耗情况，并支持手动修改 credit，通过配置文件白名单限制只有指定账号可访问。
design:
  architecture:
    framework: react
    component: shadcn
  styleKeywords:
    - 简洁专业
    - Admin 控制台
    - 数据表格
    - 语义化色彩
    - shadcn/ui
  fontSystem:
    fontFamily: Inter
    heading:
      size: 30px
      weight: 700
    subheading:
      size: 14px
      weight: 400
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#18181B"
      - "#27272A"
      - "#3F3F46"
    background:
      - "#FFFFFF"
      - "#F4F4F5"
      - "#FAFAFA"
    text:
      - "#09090B"
      - "#71717A"
      - "#A1A1AA"
    functional:
      - "#16A34A"
      - "#DC2626"
      - "#2563EB"
todos:
  - id: backend-config
    content: 在 settings.py 的 Config 类中添加 admin_allowed_emails 白名单配置字段
    status: completed
  - id: backend-super-admin-dependency
    content: 在 autogpt_libs/auth/dependencies.py 中创建 requires_super_admin 依赖，结合 admin 角色校验和邮箱白名单过滤
    status: completed
    dependencies:
      - backend-config
  - id: backend-user-list-api
    content: 在 features/admin/ 下创建 user_admin_routes.py，实现 GET /admin/users 端点，聚合查询用户信息、余额和消费量，支持分页和搜索
    status: completed
    dependencies:
      - backend-super-admin-dependency
  - id: backend-register-route
    content: 在 rest_api.py 中注册新的 user_admin_routes，使用 /api/admin 前缀
    status: completed
    dependencies:
      - backend-user-list-api
  - id: frontend-types-client
    content: 在 types.ts 和 client.ts 中添加 AdminUserSummary 类型定义和 listAllUsers API 方法
    status: completed
  - id: frontend-user-page
    content: 完整实现 admin/users/page.tsx 用户管理页面，含搜索、分页表格、credit 修改功能，复用 AddMoneyButton 和 PaginationControls 组件
    status: completed
    dependencies:
      - frontend-types-client
      - backend-user-list-api
  - id: frontend-sidebar-update
    content: 更新 admin/layout.tsx 侧边栏，将 Admin User Management 链接从 /admin/settings 改为 /admin/users
    status: completed
    dependencies:
      - frontend-user-page
---

## 产品概述

为 AutoGPT 项目添加运维端用户管理界面，管理员可以查看平台上所有用户的完整画像，包括基本信息、当前积分余额和历史消耗情况，并能够手动调整任意用户的积分。

## 核心功能

- **用户列表查询**：以分页表格形式展示所有用户，包含用户名（邮箱+姓名）、当前 credit 余额、累计消费量，支持搜索过滤
- **Credit 手动修改**：管理员可为任意用户手动增加或扣除积分，填写金额和备注，操作记录可追溯
- **白名单访问控制**：通过配置文件指定允许访问的邮箱白名单，结合 admin 角色双重验证，确保仅项目拥有者账号可以进入运维端

## 技术栈

- **后端**：Python FastAPI + Prisma ORM + PostgreSQL + Supabase Auth JWT
- **前端**：Next.js App Router + React + TypeScript + Tailwind CSS
- **复用组件**：现有 Table、PaginationControls、AddMoneyButton、useToast 等

## 实现方案

### 后端实现策略

**1. 配置层 — 添加白名单字段**

在 `settings.py` 的 `Config` 类中新增 `admin_allowed_emails` 字段（逗号分隔的邮箱列表），通过环境变量或配置文件注入。这样运维人员只需修改部署配置即可控制谁能访问运维端。

**2. 认证层 — 创建超级管理员依赖**

在 `autogpt_libs/auth/dependencies.py` 中新增 `requires_super_admin` 依赖函数，逻辑链路：

1. 先调用已有的 `requires_admin_user` 验证 JWT 中 `role == "admin"`
2. 再读取 `Settings().config.admin_allowed_emails` 配置
3. 若白名单为空则允许所有 admin 访问（向后兼容）；若配置了白名单，则仅允许邮箱在白名单中的 admin

这种双层防护既保留了现有 admin 体系，又增加了白名单过滤。

**3. 数据层 — 聚合查询用户与积分**

新建 API 端点 `GET /admin/users`，在 `features/admin/user_admin_routes.py` 中实现。查询策略：

- 使用 Prisma 批量查询 `User` 表获取用户基本信息（id、email、name、createdAt）
- 批量查询 `UserBalance` 表获取当前余额
- 对 `CreditTransaction` 表按 `userId` 分组，统计 `type=USAGE` 且 `isActive=true` 的记录求和，得到总消费量
- 支持分页（page/page_size）和搜索（按 email 或 name 模糊匹配）
- 排序：按创建时间倒序

性能考量：一次查询同时获取用户列表和余额，避免 N+1 问题。消费量统计按 `SUM(amount)` 聚合。数据量较大时依赖 PostgreSQL 的 `@@index([userId, createdAt])` 索引。

**4. 路由注册**

在 `rest_api.py` 中以 `prefix="/api/admin"` 注册新路由，与现有 admin 路由风格一致。

### 前端实现策略

**1. API Client 层**

在 `client.ts` 中新增 `listAllUsers(params)` 方法，调用 `GET /admin/users`。在 `types.ts` 中新增 `AdminUserSummary` 类型（含 user_id、email、name、balance、total_consumption）和 `AdminUsersListResponse`（含分页信息）。

**2. 页面层 — 用户管理界面**

完全替换占位页面 `admin/users/page.tsx`，参考 `admin/spending/page.tsx` 的实现模式：

- 使用 `withRoleAccess(["admin"])` 进行服务端权限校验
- 使用 Suspense 包裹数据加载组件
- 使用已有的 `Table`、`TableHeader`、`TableRow` 等组件构建用户列表
- 复用 `AddMoneyButton` 实现积分修改（已支持弹窗输入金额和备注）
- 使用 `PaginationControls` 实现分页
- 添加搜索输入框支持按邮箱/用户名过滤
- 显示字段：用户名（name/email）、当前余额、累计消费、注册时间、操作按钮

**3. 导航更新**

修改 `admin/layout.tsx` 中 "Admin User Management" 的链接，从 `/admin/settings` 改为 `/admin/users`，并更换为更合适的图标。

## 实现注意事项

- **向后兼容**：`admin_allowed_emails` 为空时，所有 admin 角色用户均可访问，不影响已有功能
- **安全审计**：所有 credit 修改操作均记录 admin_user_id，已有 credit_admin_routes 的 add_credits 端点已实现此功能，直接复用
- **性能**：用户列表查询使用分页（默认 20 条/页），消费量使用 SQL 聚合避免加载全量交易记录
- **日志**：复用项目已有的 `logging.getLogger(__name__)` 模式，关键操作记录 info 级别日志
- **错误处理**：沿用项目现有 `HTTPException` 和 `DatabaseError` 模式

## 设计风格

采用与现有 Admin 面板一致的简洁专业风格，延用项目已有的 shadcn/ui 组件体系。页面以白色卡片式表格为主体，搭配灰色背景，使用绿色/红色语义化色彩区分余额正负，整体呈现清晰的数据管理体验。

## 页面设计 — 运维端用户管理页

### 顶部标题区

左侧显示「用户管理」大标题和「查看和管理所有用户的积分信息」副标题，延续 spending 页面的标题风格。使用与 spending 页面一致的 flex 布局和字体层级。

### 搜索过滤栏

居中放置搜索输入框，支持按用户邮箱或姓名实时搜索。输入框采用圆角边框设计，左侧带搜索图标，placeholder 提示「搜索用户邮箱或姓名…」。复用已有的 `SearchAndFilterAdminSpending` 组件模式。

### 用户数据表格

白色圆角卡片包裹的表格，表头灰底白字。列依次为：用户名（姓名+邮箱）、当前余额（绿色显示）、累计消费（红色显示）、注册时间、操作按钮。每一行悬停时呈现浅灰背景高亮。余额和消费以美元格式展示（$X.XX）。

### 操作列

每行右侧放置「调整积分」按钮（复用 AddMoneyButton 组件），点击弹出模态对话框，展示用户当前余额、金额输入框（美元单位）、备注文本框，确认后提交。

### 底部分页

底部居中显示分页控件（复用 PaginationControls），显示当前页码和总页数，支持前后翻页。

## Agent Extensions

### SubAgent

- **code-explorer**
- 用途：在实现过程中快速定位和验证现有代码模式、API 签名、类型定义
- 预期结果：确保新增代码与现有项目的 import 路径、函数签名、组件接口完全一致
---
name: workspace-file-management
overview: 为 AutoGPT 工作空间添加完整的文件管理功能，包括前端文件浏览页面和后端文件重命名/元数据修改 API。
design:
  architecture:
    framework: react
  styleKeywords:
    - 简洁工作台
    - 专业管理后台
    - 与 Copilot 风格一致
    - 功能优先
  fontSystem:
    fontFamily: Inter
    heading:
      size: 20px
      weight: 600
    subheading:
      size: 14px
      weight: 500
    body:
      size: 13px
      weight: 400
  colorSystem:
    primary:
      - "#3B82F6"
      - "#2563EB"
    background:
      - "#FFFFFF"
      - "#F9FAFB"
      - "#F3F4F6"
    text:
      - "#111827"
      - "#6B7280"
      - "#9CA3AF"
    functional:
      - "#EF4444"
      - "#10B981"
      - "#F59E0B"
todos:
  - id: backend-rename-endpoint
    content: 后端新增文件重命名功能：在 data/workspace.py 添加 update_workspace_file 函数，在 util/workspace.py 添加 rename_file 方法，在 routes.py 添加 PATCH /files/{file_id} 端点
    status: completed
  - id: regenerate-openapi
    content: 重新生成 OpenAPI spec 并运行 Orval 生成前端 API client（含 PATCH rename 和 list/delete hooks）
    status: completed
    dependencies:
      - backend-rename-endpoint
  - id: frontend-file-manager-page
    content: 新建文件管理页面核心组件：FileManagerPage.tsx（含 StorageBar 集成、工具栏、文件列表、分页器）和 useFileManager.ts hook
    status: completed
    dependencies:
      - regenerate-openapi
  - id: frontend-file-row-dialogs
    content: 新建文件操作子组件：FileRow.tsx（含复选框和操作菜单）、RenameFileDialog.tsx、DeleteConfirmDialog.tsx、FileTableHeader.tsx
    status: completed
    dependencies:
      - frontend-file-manager-page
  - id: storagebar-entry-link
    content: 修改 StorageBar.tsx 添加「管理文件」入口链接，指向 /copilot/files
    status: completed
    dependencies:
      - frontend-file-manager-page
  - id: mobile-responsive-polish
    content: 完善移动端响应式布局：卡片列表视图、移动端操作菜单、适配小屏间距和字号
    status: completed
    dependencies:
      - frontend-file-row-dialogs
---

## 用户需求

目前 AutoGPT 项目中发送给 LLM 的文件会被保存到工作空间中（限制 250MB），但用户只能通过 `StorageBar` 组件看到已用空间和文件数量，无法进入空间管理文件。需要加入完整的文件管理功能。

## 产品概述

为 AutoGPT Copilot 添加一个工作空间文件管理页面，允许用户浏览、搜索、重命名和删除工作空间中的文件，释放存储空间。

## 核心功能

- **文件浏览**：分页展示工作空间所有文件，显示文件名、类型、大小、创建日期
- **文件删除**：支持单个文件删除和批量选择删除，带确认对话框
- **文件重命名**：支持修改文件名，更新路径以保持一致性
- **入口集成**：在现有 StorageBar 组件中添加「管理文件」链接入口
- **响应式设计**：适配桌面和移动端，桌面端为表格视图，移动端为卡片列表

## 技术栈

- **前端**: Next.js (App Router) + React 18 + TypeScript + Tailwind CSS
- **后端**: Python FastAPI + Prisma ORM
- **图标**: @phosphor-icons/react
- **状态管理**: @tanstack/react-query（Orval 自动生成 hooks）
- **API 规范**: OpenAPI 3.0（`src/app/api/openapi.json`）

## 实现方案

### 整体策略

采用「后端新增重命名端点 → 更新 OpenAPI spec → 前端通过 Orval 自动生成 API client → 新建文件管理页面」的流程。前端复用项目现有的 Button、Dialog、Text、Toast 组件和定制钩子模式，与现有 StorageBar 无缝集成。

### 后端变更

#### 1. 数据层新增 `update_workspace_file` 函数（`data/workspace.py`）

- 按 `file_id` + `workspace_id` 查找文件
- 更新 `name` 字段和 `path` 字段（path 需同步更新以保持路径一致性）
- 返回更新后的 `WorkspaceFile`

#### 2. WorkspaceManager 新增 `rename_file` 方法（`util/workspace.py`）

- 接收 `file_id` 和 `new_name`
- 从旧 path 提取目录前缀，拼接新文件名生成新 path
- 检查新 path 是否已存在（同名冲突检测）
- 调用数据层更新 name 和 path
- 返回更新后的 `WorkspaceFile`

#### 3. API 路由新增 PATCH 端点（`api/features/workspace/routes.py`）

- `PATCH /api/workspace/files/{file_id}` — 重命名文件
- 请求体：`{ "name": "new_filename.txt" }`
- 响应体：`{ "id", "name", "path", "mime_type", "size_bytes", "metadata", "created_at" }`
- 错误处理：404（文件不存在）、409（名称冲突）

### 前端变更

#### 1. 新建文件管理页面 `src/app/(platform)/copilot/files/page.tsx`

- "use client" 页面
- 渲染 `FileManagerPage` 组件
- 页面路由：`/copilot/files`

#### 2. 新建 `FileManagerPage` 组件（`components/FileManager/FileManagerPage.tsx`）

- 顶部 Header：标题「文件管理」+ StorageBar 摘要 + 批量操作按钮
- 中间文件列表：分页表格（桌面）/ 卡片列表（移动）
- 每行：复选框、文件名、类型图标、大小、日期、操作按钮（重命名、删除、下载）
- 分页控件（上一页/下一页，has_more 驱动）

#### 3. 新建专用 Hook `useFileManager.ts`

- 封装 `useListWorkspaceFiles`（分页查询）、`useDeleteWorkspaceFile`（删除 mutation）
- 管理选中状态（Set）、分页状态（offset/limit）
- 处理删除成功后的列表刷新和 toast 通知

#### 4. 新建子组件

- `FileRow.tsx` — 单行文件记录，含复选框、操作菜单
- `RenameFileDialog.tsx` — 重命名对话框，含输入验证
- `DeleteConfirmDialog.tsx` — 删除确认对话框（单个/批量）
- `FileTableHeader.tsx` — 表头含全选复选框

#### 5. 修改 StorageBar 添加入口

- 在 `StorageBar.tsx` 底部添加「管理文件」链接按钮
- 使用 Next.js `Link` 组件指向 `/copilot/files`

### 关键设计决策

- **重命名仅改 DB 记录**：文件名和 path 都在数据库中，无需触碰物理存储，性能开销极低
- **删除复用现有软删除**：后端已有完善的 DELETE 端点，前端直接调用
- **分页沿用现有模式**：limit/offset + has_more 与现有 list API 保持一致
- **移动端卡片布局**：使用 Tailwind `hidden md:table-cell` / `md:hidden` 实现响应式切换

### 实现注意事项

- OpenAPI spec 需在添加后端端点后重新生成（`python scripts/generate_openapi.py` 或等效命令），Orval 才能生成含 PATCH 的 client
- API proxy 路径：前端通过 `/api/proxy/workspace/files/...` 代理到后端，Orval 生成的 client 自动处理
- 使用 `queryClient.invalidateQueries` 在删除/重命名后刷新列表
- 批量删除使用 `Promise.allSettled` 处理部分失败，通过 toast 汇总结果
- StorageBar 入口仅在 `file_count > 0` 时显示

## 设计风格

沿用项目现有的 Copilot 设计语言，采用简洁专业的工作台风格，与 StorageBar、UsageLimits 等组件视觉一致。

## 页面结构

### 文件管理页面（/copilot/files）

采用「顶部状态栏 + 工具栏 + 主体列表 + 分页器」的经典管理后台布局。

**Block 1 — 页面标题栏**

- 左侧「工作空间文件」标题（Text h4）+ 面包屑导航
- 右侧返回 Copilot 按钮（ghost variant）

**Block 2 — 存储概览条**

- 复用 StorageBar 的进度条样式，展示已用/总空间和文件数
- 紧凑模式，高度较原组件缩小，融入页面头部

**Block 3 — 工具栏**

- 左侧：已选 N 个文件的批量操作区（选中时出现「删除所选」按钮，destructive variant）
- 右侧：搜索输入框（按文件名过滤）+ 视图切换图标（列表/网格，预留）

**Block 4 — 文件列表（桌面端）**

- 表头行：复选框（全选）、名称、类型、大小、日期、操作
- 数据行：每行显示文件图标（按 MIME 类型）、文件名、MIME 类型标签、格式化大小、创建日期、操作按钮组（重命名图标、下载图标、删除图标）
- 悬停高亮行，空状态显示插图 + 提示文案

**Block 5 — 文件列表（移动端）**

- 卡片列表替代表格，每张卡片显示文件名（主标题）、类型+大小（副标题）、日期（底部）
- 卡片右侧三个点菜单触发操作选项

**Block 6 — 分页器**

- 底部分页控件：上一页/下一页按钮 + 「第 X 页」文字
- 基于 has_more 标志控制按钮禁用状态

### 对话框

- **重命名对话框**：标题「重命名文件」，输入框预填当前文件名，校验非空和非法字符，确定/取消按钮
- **删除确认对话框**：标题「删除文件」/「删除所选文件」，列出文件名，警告文案，确定(红色)/取消按钮

## 子代理

- **code-explorer**
- 用途：在实施过程中搜索和定位相关代码模式，确认现有组件 API 签名和导入路径
- 预期结果：准确定位需要修改的文件和可复用的组件/工具函数
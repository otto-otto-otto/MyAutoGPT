---
name: add-workspace-nav-link
overview: 在导航栏 Home 右侧新增 Workspace 链接，点击直接进入 /copilot/files（Manage Files 页面），支持桌面端和移动端。
todos:
  - id: add-icon-type
    content: 在 icons.tsx 的 IconType 枚举中新增 Workspace 成员
    status: completed
  - id: update-helpers
    content: 在 helpers.tsx 中：loggedInLinks 添加 Workspace 条目，getAccountMenuOptionIcon 添加 Workspace→FolderOpen 映射
    status: completed
    dependencies:
      - add-icon-type
  - id: update-navbar-link
    content: 在 NavbarLink.tsx 中添加 /copilot/files 的 FolderOpen 图标条件渲染
    status: completed
  - id: update-mobile-nav
    content: 在 Navbar.tsx 移动端菜单中新增 /copilot/files→IconType.Workspace 映射
    status: completed
    dependencies:
      - add-icon-type
---

## 用户需求

在顶部导航栏 Home 链接的右侧新增 Workspace 链接，点击后直接进入 Manage Files 页面（路由 `/copilot/files`）。需要同时在桌面端和移动端导航中展示。

## 核心功能

- 桌面端导航栏：Home 右侧显示 Workspace 链接，带文件夹图标
- 移动端弹出菜单：同样显示 Workspace 导航项
- 点击 Workspace 直接跳转到 `/copilot/files` 文件管理页面

## 技术方案

### 修改文件（共4个文件）

#### 1. `icons.tsx` — IconType 枚举新增 Workspace

- 在 `IconType` 枚举末尾新增 `Workspace` 成员
- 位置：`src/components/__legacy__/ui/icons.tsx` 第1829行

#### 2. `helpers.tsx` — 两处修改

- **loggedInLinks 数组**：添加 `{ name: "Workspace", href: "/copilot/files" }`，使其出现在 Home 右侧
- **getAccountMenuOptionIcon 函数**：添加 `case IconType.Workspace` 分支，返回 `FolderOpen` 图标（phosphor-icons，与 StorageBar 中 Manage files 图标一致，需新增 import）

#### 3. `NavbarLink.tsx` — 桌面端图标渲染

- 添加 `href === "/copilot/files"` 条件，渲染 `FolderOpen` 图标（从 `@phosphor-icons/react` 引入）
- 遵循现有图标样式模式：`iconBaseClass` + 激活态 `text-white`

#### 4. `Navbar.tsx` — 移动端菜单映射

- 在移动端 `actualLoggedInLinks.map()` 的图标映射中（第129-138行），新增 `/copilot/files` → `IconType.Workspace` 的条件分支

### 实现要点

- 复用现有 `FolderOpen` (phosphor-icons)，与 StorageBar 中的 Manage files 图标保持一致
- 遵循现有 link 模式：`loggedInLinks` 数组追加条目即自动出现在 Home 右侧，无需修改核心 Navbar 渲染逻辑
- 移动端图标通过 `IconType.Workspace` → `getAccountMenuOptionIcon` → `FolderOpen` 的链路渲染
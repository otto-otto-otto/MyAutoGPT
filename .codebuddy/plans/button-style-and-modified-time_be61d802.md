---
name: button-style-and-modified-time
overview: 缩小文件操作按钮并去掉圆形边框，同时在创建时间右侧新增"修改时间"列
todos:
  - id: backend-add-updated-at
    content: 后端 routes.py：WorkspaceFileItem 模型新增 updated_at 字段，并在 list_files 和 rename 响应中填充
    status: completed
  - id: openapi-add-updated-at
    content: openapi.json：WorkspaceFileItem schema 新增 updated_at 属性
    status: completed
    dependencies:
      - backend-add-updated-at
  - id: frontend-type-add-updated-at
    content: 前端 workspaceFileItem.ts 类型新增 updated_at 字段
    status: completed
    dependencies:
      - openapi-add-updated-at
  - id: table-header-add-updated
    content: FileTableHeader.tsx：在 Created 和 actions 之间新增 Updated 列表头
    status: completed
  - id: filerow-shrink-buttons-and-add-updated
    content: FileRow.tsx：操作按钮改为无边框紧凑原生 button；新增 updated_at 列；文件名改为可点击触发下载
    status: completed
    dependencies:
      - frontend-type-add-updated-at
      - table-header-add-updated
  - id: page-shrink-buttons-and-add-updated
    content: FileManagerPage.tsx：移动端卡片操作按钮同步改为无边框紧凑样式；新增修改时间展示；文件名改为可点击触发下载
    status: completed
    dependencies:
      - frontend-type-add-updated-at
---

## 用户需求

1. 文件管理页面的操作按钮（重命名、下载、删除）进一步缩小，并去掉圆形边框样式
2. 在创建时间列右侧新增"修改时间"（updated_at）列，展示文件最近一次修改的时间
3. 点击文件名可以直接在本地下载/打开文件

## 产品概览

对现有 FileManager 文件列表进行三项 UI 增强：(1) 操作按钮从带圆圈边框的 icon variant 改为无边框紧凑纯图标按钮；(2) 新增修改时间列，前后端数据模型同步更新以支持 updated_at 字段；(3) 文件名变为可点击链接，点击触发浏览器下载打开本地文件。

## 核心功能

- 操作按钮改为无边框、p-1.5 紧凑纯图标按钮，hover 时浅色背景，删除按钮红色系
- 桌面端列表和移动端卡片均新增"修改时间"展示
- 后端 API 响应模型新增 updated_at 字段，从现有 data 层的 WorkspaceFile.updated_at 透传
- 桌面端和移动端文件名改为可点击，复用现有 downloadFile（blob URL + 隐藏 a 标签触发下载）

## 技术方案

### 1. 按钮样式改造

**问题**：当前 `variant="icon" size="icon"` 使用 Button 组件，该 variant 固定带 `border border-zinc-300 rounded-[96px] p-3`，产生圆形边框 + 12px 内边距，视觉上像"圆圈圈住"且过大。

**方案**：放弃 Button 组件的 `icon` variant，改用原生 `<button>` 元素，以极简样式实现纯图标按钮：

- 无边框（无圆圈）
- `p-1.5`（6px 内边距，远小于 p-3 的 12px）
- 小圆角 `rounded`（4px），不产生圆形效果
- `text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800 transition-colors`
- 删除按钮红色系：`text-red-500 hover:text-red-600 hover:bg-red-50`
- 保留 `aria-label` 确保无障碍

**影响文件**：

- `FileRow.tsx` 第153-181行：替换三个 Button 为原生 button
- `FileManagerPage.tsx` 第336-366行：移动端卡片同样替换

### 2. 新增 updated_at 列

**数据流**：`DB UserWorkspaceFile.updatedAt` → `WorkspaceFile.updated_at` (已存在于 data 层) → `WorkspaceFileItem.updated_at` (API 层，需新增) → 前端类型 → UI 展示

**后端修改**（`routes.py`）：

- `WorkspaceFileItem` 模型新增字段：`updated_at: str`
- list_files 映射（L433）：添加 `updated_at=f.updated_at.isoformat()`
- rename 响应（L263）：添加 `updated_at=updated.updated_at.isoformat()`

**openapi.json**：

- WorkspaceFileItem schema 新增 `updated_at` 属性并加入 required

**前端类型**（`workspaceFileItem.ts`）：

- 接口新增 `updated_at: string`

**前端 UI**：

- `FileTableHeader.tsx`：在 Created 列和操作占位列之间插入 Updated 列表头
- `FileRow.tsx`：在 created_at 列和 actions 列之间插入 updated_at 日期展示列
- `FileManagerPage.tsx`：移动端卡片在日期行添加修改时间

### 3. 文件名点击下载

**方案**：FileRow 新增 `onOpenFile` 回调 prop，触发时调用 `downloadFile`。文件名 Text 改为 `<button>`，添加 `cursor-pointer` 和 hover 色变。

- `FileRow.tsx` Props 新增 `onOpenFile: () => void`；文件名包裹为 `<button onClick={onOpenFile}>`
- `FileManagerPage.tsx`：传入 `handleDownload(file)` 作为 `onOpenFile`
- 移动端卡片同步处理

### 实现注意事项

- 按钮改为原生 button 后不再有 Button 组件的自动 tooltip，但保留了 `aria-label` 用于无障碍
- `updated_at` 字段在后端 data 层已完整支持（`WorkspaceFile.updated_at`、`from_db` 映射），仅需 API 层和前端透传
- 修改时间与创建时间使用相同的日期格式化方式
- 文件名点击复用现有 downloadFile 逻辑（blob URL + 隐藏 a 标签），不新增后端接口
---
name: fix-file-action-button-spacing
overview: 缩小文件管理页面操作按钮间距，修复3个按钮溢出遮挡创建日期的问题
todos:
  - id: fix-filerow-gap
    content: 修改 FileRow.tsx 第151行：将 actions 容器的 `gap-1` 改为 `gap-0`
    status: completed
  - id: fix-page-gap
    content: 修改 FileManagerPage.tsx 第320行：将移动端 actions 容器的 `gap-1` 改为 `gap-0`
    status: completed
---

## 问题描述

文件管理前端页面中，操作按钮（重命名/下载/删除）之间的间距过大，导致操作列溢出，遮挡了右侧的创建日期列。

## 根因分析

- FileRow.tsx 第151行 actions 容器：`w-24` (96px) + `gap-1` (4px×2个间隙=8px)
- 三个 icon 按钮各 32px (h-8 w-8)，总宽度 96px + 8px = **104px**，超出容器宽度 96px
- 溢出部分遮挡右侧 Date 列（w-36, 144px）
- FileManagerPage.tsx 第320行移动端卡片视图中 actions 容器也使用 `gap-1`

## 修复目标

将两处 actions 容器的 `gap-1` 改为 `gap-0`，使 3×32=96px 刚好适配 `w-24` 容器，操作按钮紧贴排列，不再溢出遮挡日期列。

## 修改文件清单

### 1. FileRow.tsx（桌面端文件行组件）

- **路径**: `autogpt_platform/frontend/src/app/(platform)/copilot/components/FileManager/FileRow.tsx`
- **第151行**: `<div className="flex w-24 shrink-0 items-center justify-end gap-1">`
- **修改为**: `<div className="flex w-24 shrink-0 items-center justify-end gap-0">`
- **效果**: 三个操作按钮（重命名、下载、删除）紧贴排列，总宽 96px 完美适配容器

### 2. FileManagerPage.tsx（移动端卡片视图）

- **路径**: `autogpt_platform/frontend/src/app/(platform)/copilot/components/FileManager/FileManagerPage.tsx`
- **第320行**: `<div className="flex shrink-0 items-center gap-1">`
- **修改为**: `<div className="flex shrink-0 items-center gap-0">`
- **效果**: 移动端同样消除按钮间距，防止溢出

### 技术细节

- Tailwind `gap-0` 等价于 CSS `gap: 0px`，完全消除 flex 容器内子元素间距
- 修改仅影响 CSS class，不影响任何逻辑或类型
- 无需重新生成 API 客户端
---
name: toast-click-dismiss
overview: 移除 toast 消息的 X 关闭按钮，并实现点击网页任意位置消除最新一条 toast 消息的功能。
todos:
  - id: modify-toaster
    content: 修改 toaster.tsx：移除 closeButton prop，添加全局 click 监听器实现点击任意位置消除最新一条 toast
    status: pending
---

## 用户需求

当前项目底部 toast 消息右上角有一个 X 关闭按钮，用户必须精确点击该按钮才能消除消息，操作不便。需要：

1. 去掉 toast 消息的 X 关闭按钮
2. 改为点击页面任意位置即可消除最新一条 toast 消息（每次点击只消除一条，不是全部消除）

## 产品概览

简化 toast 交互体验：移除 X 关闭按钮，用户不再需要精确点击小按钮；改为点击页面任意空白区域即可逐条消除 toast，操作更自然、便捷。

## 核心功能

- 移除 sonner Toaster 的 `closeButton` 配置，X 按钮不再显示
- 在 Toaster 组件内添加全局 click 事件监听
- 点击时获取最新一条活跃 toast，调用 sonner 的 dismiss API 消除该条
- 如果没有任何活跃 toast，点击无效果

## 技术方案

### 修改文件

仅修改一个文件：`toaster.tsx`

### 实现方式

1. **移除 X 按钮**：删除 `<SonnerToaster>` 上的 `closeButton` prop（当前第11行）
2. **新增全局点击监听**：在 `Toaster` 组件内使用 `useEffect` 注册 `document.addEventListener("click", ...)` 事件
3. **消除最新 toast**：在点击回调中调用 `import { toast } from "sonner"` 的 `toast.getToasts()` 获取所有活跃 toast 数组，取数组最后一个元素（最新创建的 toast），调用 `toast.dismiss(latestToast.id)` 消除
4. **清理副作用**：在 `useEffect` 的 cleanup 中移除事件监听

### 关键点

- sonner 的 `toast.getToasts()` 返回的数组按创建时间升序排列，最后一个元素即为最新 toast
- 点击后只消除一条，不是全部（区别于 `toast.dismiss()` 无参调用）
- 当没有活跃 toast 时点击无任何反应，不会报错
- 事件监听在组件卸载时正确移除，防止内存泄漏
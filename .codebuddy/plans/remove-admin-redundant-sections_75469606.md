---
name: remove-admin-redundant-sections
overview: 从运维端（Admin Panel）移除 Marketplace Management、Execution Analytics、Block Cost Estimates 三个冗余模块，包括导航项、页面目录和相关引用。
todos:
  - id: clean-layout-tsx
    content: 从 layout.tsx 侧边栏导航中删除 3 个冗余模块（Marketplace/Execution Analytics/Block Cost Estimates），并清理未使用的 icon 导入
    status: completed
  - id: fix-test
    content: 从 layout.test.tsx 中移除已删除导航项的断言
    status: completed
    dependencies:
      - clean-layout-tsx
  - id: fix-navbar-entry
    content: 将 helpers.tsx 和 AccountMenu.stories.tsx 中 Admin 入口链接从 /admin/marketplace 改为 /admin/dashboard
    status: completed
    dependencies:
      - clean-layout-tsx
  - id: delete-page-dirs
    content: 删除 marketplace、execution-analytics、block-cost-estimates 三个页面目录
    status: completed
    dependencies:
      - clean-layout-tsx
---

## 用户需求

从运维端（Admin Panel）移除三个冗余模块的导航入口及相关代码：

- Marketplace Management
- Execution Analytics  
- Block Cost Estimates

## 修改范围

共涉及 5 处修改 + 3 个目录删除：

1. 侧边栏导航定义（layout.tsx）：删除 3 个导航项及对应未使用的 icon 导入
2. 侧边栏单元测试（layout.test.tsx）：删除 2 条已失效的断言
3. 顶栏 Admin 入口（helpers.tsx）：将链接从 `/admin/marketplace` 改为 `/admin/dashboard`
4. Storybook 故事（AccountMenu.stories.tsx）：同步更新链接
5. 删除 3 个页面目录及其全部文件

## 修改详情

### 涉及文件及改动

**1. layout.tsx — 侧边栏导航** `[MODIFY]`

- 从 `sidebarLinkGroups[0].links` 数组中删除 3 个对象（Marketplace Management、Execution Analytics、Block Cost Estimates）
- 从 `@phosphor-icons/react/dist/ssr` 的 import 中删除 `Users`、`FileText`、`CalculatorIcon`（不再被引用）

**2. layout.test.tsx — 单元测试** `[MODIFY]`

- 删除第 44 行：`expect(screen.getByText("Marketplace Management")).toBeDefined();`
- 删除第 50 行：`expect(screen.getByText("Execution Analytics")).toBeDefined();`

**3. helpers.tsx — 顶栏导航** `[MODIFY]`

- 第 125 行 `href: "/admin/marketplace"` 改为 `href: "/admin/dashboard"`

**4. AccountMenu.stories.tsx — Storybook** `[MODIFY]`

- 第 64 行 `href: "/admin/marketplace"` 改为 `href: "/admin/dashboard"`

**5. 删除 3 个页面目录** `[DELETE]`

- `frontend/src/app/(platform)/admin/marketplace/`
- `frontend/src/app/(platform)/admin/execution-analytics/`
- `frontend/src/app/(platform)/admin/block-cost-estimates/`
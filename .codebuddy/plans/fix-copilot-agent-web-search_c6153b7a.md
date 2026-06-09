---
name: fix-copilot-agent-web-search
overview: 修复 Copilot 层 `web_search` 工具中 Tavily 和 Serper 搜索后端未实现的问题，同时修复 `is_available` 属性不一致、DDGS 客户端资源泄漏等问题。
todos:
  - id: implement-tavily-backend
    content: 在 web_search.py 中实现 _search_tavily 异步搜索方法，使用 aiohttp 调用 Tavily API，返回 (results, answer) 元组
    status: completed
  - id: implement-serper-backend
    content: 在 web_search.py 中实现 _search_serper 异步搜索方法，使用 aiohttp 调用 Serper.dev API，返回 WebSearchResult 列表
    status: completed
  - id: refactor-search-dispatch
    content: 重构 _search_web 分发函数，移除 NotImplementedError，接入 Tavily/Serper 实现；更新 _execute 中 answer 字段赋值逻辑
    status: completed
    dependencies:
      - implement-tavily-backend
      - implement-serper-backend
  - id: fix-is-available
    content: 修复 WebSearchTool.is_available 属性，使 Tavily/Serper 根据 API key 存在与否正确返回可用性
    status: completed
    dependencies:
      - implement-tavily-backend
      - implement-serper-backend
  - id: fix-ddgs-resource-leak
    content: 修复 _search_ddgs 中 DDGS 客户端资源泄漏，改用 with 上下文管理器确保连接释放
    status: completed
  - id: update-tests
    content: 更新 web_search_test.py，新增 Tavily/Serper 后端单元测试，修正 is_available 相关测试断言
    status: completed
    dependencies:
      - refactor-search-dispatch
      - fix-is-available
      - fix-ddgs-resource-leak
---

## 用户需求

检查并修复 AutoGPT 项目中 Copilot 和 Agent 的联网搜索功能。经过代码审查，Agent Block 层搜索（百度、搜狗、Exa、Firecrawl、Jina、Wikipedia 等）运行正常；主要问题集中在 Copilot 工具层的 `web_search.py` 中。

## 核心修复项

1. **实现 Tavily 和 Serper 搜索后端**：当前代码对这两个付费搜索 provider 抛出 `NotImplementedError`，导致配置了 API key 的用户无法使用。需参考 Forge 层已有实现，为 Copilot 层编写异步版本。
2. **修复 `is_available` 逻辑**：当用户配置 Tavily/Serper provider 且有 API key 时，`is_available` 错误地返回 `True`，但实际调用会崩溃。应在实现完成前返回 `False`，实现完成后正确判断。
3. **消除 DDGS 客户端资源泄漏**：`_search_ddgs` 每次调用创建新的 `DDGS()` 客户端但从不关闭，改用上下文管理器确保资源释放。
4. **更新测试覆盖**：为新增的 Tavily/Serper 实现补充单元测试，修正现有 `is_available` 测试的错误断言。

## 技术栈选择

- **Python 3** + **aiohttp**（项目已有依赖，用于异步 HTTP 请求）
- **ddgs** 库（已安装，`^9.9`）
- **pytest** + **unittest.mock**（现有测试框架）
- 无需新增外部依赖：Tavily 和 Serper API 调用通过 `aiohttp` 直接发送 HTTP 请求，不引入额外的 SDK 包

## 实现方案

### 整体策略

参考 Forge 层 `classic/forge/forge/components/web/search.py` 中已完整实现的 `_search_tavily` 和 `_search_serper` 方法，将其同步的 `requests` 调用改造为 `aiohttp` 异步调用，并适配 Copilot 层的数据模型和错误处理风格。

### 关键设计决策

1. **复用 `aiohttp` 而非引入新 SDK**：项目已广泛使用 `aiohttp`（`web_fetch.py`、`request.py` 等），保持技术栈统一，避免引入 `tavily-python` 等新依赖。Tavily/Serper 的 REST API 足够简单，直接 HTTP 调用即可。
2. **统一超时和错误处理**：复用 `web_fetch.py` 中 `_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)` 的超时模式，保持工具间行为一致。
3. **数据模型向后兼容**：现有 `WebSearchResult(title, url, snippet, page_age)` 和 `WebSearchResponse` 保持不变，确保前端渲染不受影响。
4. **DDGS 资源管理**：使用 `DDGS.__enter__/__exit__` 上下文管理器协议确保 HTTP 会话释放。

### 实现细节

#### 1. 新增 `_search_tavily` 异步方法

- 使用 `aiohttp.ClientSession` 发送 POST 到 `https://api.tavily.com/search`
- 请求体: `{api_key, query, max_results, search_depth: "basic", include_answer: true, include_raw_content: false}`
- 解析返回的 `results[]` 数组映射到 `WebSearchResult`，提取 `answer` 字段
- 返回 `tuple[list[WebSearchResult], str]`（结果列表 + AI 摘要）

#### 2. 新增 `_search_serper` 异步方法

- 使用 `aiohttp.ClientSession` 发送 POST 到 `https://google.serper.dev/search`
- Header 设置 `X-API-KEY`
- 请求体: `{q: query, num: max_results}`
- 解析返回 `organic[]` 数组，映射 `title→title`, `link→url`, `snippet→snippet`
- 返回 `list[WebSearchResult]`

#### 3. 重构 `_search_web` 分发函数

- 移除 `NotImplementedError`，改为调用 `_search_tavily` / `_search_serper`
- 传入 `_chat_config` 的 API key
- 统一异常包装，让上层 `WebSearchTool._execute` 的 try/except 统一捕获

#### 4. 修复 `_search_ddgs` 资源管理

- 将 `client = DDGS()` 改为 `with DDGS() as client:` 上下文管理器
- `asyncio.to_thread` 需在上下文管理器内部使用（同步的 `client.text` 调用本身不需要 async context manager，但 DDGS 资源生命期由 with 管理）

#### 5. 修复 `is_available` 属性

- Tavily: `is_available = bool(_chat_config.tavily_api_key)`（实现了就按 API key 判断）
- Serper: `is_available = bool(_chat_config.serper_api_key)`（同上）

#### 6. 更新 `_search_web` 使 Tavily/Serper 返回完整数据

- `_search_tavily` 返回 `(results, answer)`，需调整 `_search_web` 签名和 `_execute` 中的 answer 赋值
- 保持 DDGS 路径不变（answer 为空字符串）

### 性能与可靠性

- Tavily/Serper 每次搜索仅一次 HTTP 请求，15 秒超时
- DDGS 8 引擎回退链最坏情况 8 次尝试，每次超时控制在 DDGS 库内部
- 所有网络调用均通过 `aiohttp` 异步执行，不阻塞事件循环
- DDGS 客户端每次用完即释放，避免连接池耗尽

### 目录结构

```
d:\cn gpt\AutoGPT-master\autogpt_platform\backend\backend\copilot\tools\
├── web_search.py          # [MODIFY] 核心修复文件
│   ├── 新增 _search_tavily() — Tavily 异步搜索实现
│   ├── 新增 _search_serper() — Serper 异步搜索实现
│   ├── 重构 _search_web() — 移除 NotImplementedError，接入新实现
│   ├── 修复 WebSearchTool.is_available — Tavily/Serper 按 API key 正确判断
│   └── 修复 _search_ddgs() — 使用 DDGS 上下文管理器
├── web_search_test.py     # [MODIFY] 测试文件更新
│   ├── 新增 TestSearchTavily 类 — Tavily 单元测试
│   ├── 新增 TestSearchSerper 类 — Serper 单元测试
│   └── 修正 TestWebSearchToolIsAvailable — 对齐 is_available 新逻辑
└── pyproject.toml         # 无需修改 — aiohttp 已存在
```
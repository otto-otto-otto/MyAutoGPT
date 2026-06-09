---
name: remove-agent-knowledge-from-copilot
overview: 从 Copilot AI 的提示词/上下文中移除所有 agent 自动化相关的知识注入，同时添加当前日期/时间感知能力。
todos:
  - id: rewrite-system-prompt
    content: 重写 service.py 系统提示词：将 _CACHEABLE_SYSTEM_PROMPT (L182-198) 改为通用 AI 助手身份，去除 agent/automation 使命及 builder/skills 标签说明；在 _build_system_prompt() (L511) 末尾追加当前 UTC+8 日期
    status: completed
  - id: disable-builder-context
    content: 修改 builder_context.py：build_builder_system_prompt_suffix() (L180) 和 build_builder_context_turn_prefix() (L212) 函数体内直接 return ""
    status: completed
  - id: clean-prompting-notes
    content: 清理 prompting.py：删除 AutoPilotBlock/run_sub_session 段落 (L211-216)、agent_building_guide 引用 (L229)、credentials 段落中 agent/run_agent (L318-335)、Graphiti 指令中 building an agent (L594)
    status: completed
  - id: prune-tool-registry
    content: "裁剪 tools/__init__.py：注释 12 个 agent 工具注册 (L71-76,88-89,95,103,106,131-132) 和对应 import 行 (L18-20,22,24-26,33,38,44,52)，标注 # [AGENT-REMOVED]；注释向后兼容导出 (L141-142)"
    status: completed
  - id: verify
    content: 验证：检查四个文件语法正确性，确认 TOOL_REGISTRY 中不再包含 agent 工具，通用工具不受影响
    status: completed
    dependencies:
      - rewrite-system-prompt
      - disable-builder-context
      - clean-prompting-notes
      - prune-tool-registry
---

## 用户需求

1. 删除 AI 对 agent 自动化功能的"认知/记忆"，将 Copilot 改造为纯通用 AI 助手
2. 让 AI 知道当前真实日期（2026 年 6 月），而非默认的 2025 年训练截止日期
3. 保留对话、文件操作、web 搜索、内存搜索等所有通用能力

## 核心变更

1. 重写系统提示词：去掉 agent 自动化使命，补充当前日期感知
2. 停用 Builder 上下文注入：两个公开函数改为始终返回空字符串
3. 清理工具文档中的 agent 引用
4. 裁剪工具注册表：注释 12 个 agent 专用工具及对应 import

## 技术方案

### 修改文件清单

| 文件 | 操作 | 说明 |
| --- | --- | --- |
| `service.py` L182-198, L491-512 | 重写+追加 | 系统提示词改通用身份；`_build_system_prompt()` 末尾拼接当天日期 |
| `builder_context.py` L180, L212 | 修改 | `build_builder_system_prompt_suffix()` 和 `build_builder_context_turn_prefix()` 直接 return "" |
| `prompting.py` L211-216, L229, L318-319, L324, L334, L594 | 修剪 | 删除 agent/automation 相关引用 |
| `tools/__init__.py` L18-20,22,24-26,33,38,44,52, L71-76,88-89,95,103,106,131-132,141-142 | 裁剪 | 注释 12 个 agent 工具注册 + 对应 14 行 import |


### 日期注入设计

在 `_build_system_prompt()` (L511) 中，获取系统提示词后拼接当前日期：

```python
from datetime import datetime, timezone, timedelta
today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %A")
prompt = (await _fetch_langfuse_prompt() or _CACHEABLE_SYSTEM_PROMPT) + f"\n\nCurrent date: {today} (UTC+8)."
```

- 每次会话开始时重新计算，日期变化自然生效
- 日期在系统提示词末尾追加，不影响 cacheable 前缀语义
- 可能轻微降低跨日 prompt 缓存命中率，但在本地部署场景可忽略

### 关键约束

- `builder_context` 函数保留签名只改返回逻辑，调用点（`baseline/service.py`、`sdk/service.py`）无需修改
- 工具注册表用 `# [AGENT-REMOVED]` 注释标记，方便日后恢复
- `parse_arguments` 中的 `run_block(block_id="agpt_agent_..."...)` 逻辑属于 block 运行层，不涉及 agent 概念的提示词注入，无需修改
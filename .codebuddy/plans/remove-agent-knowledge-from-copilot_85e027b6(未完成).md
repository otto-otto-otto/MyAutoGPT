---
name: remove-agent-knowledge-from-copilot
overview: 从 Copilot AI 的提示词/上下文中移除所有 agent 自动化相关的知识注入，包括系统提示词、builder 上下文、技能引用、工具文档和记忆系统。
todos:
  - id: rewrite-system-prompt
    content: 重写 service.py 中的 _CACHEABLE_SYSTEM_PROMPT，删除 agent 自动化使命和 builder/skills 标签说明，改为通用 AI 助手身份
    status: pending
  - id: disable-builder-context
    content: 修改 builder_context.py 中 build_builder_system_prompt_suffix() 和 build_builder_context_turn_prefix()，使其始终返回空字符串
    status: pending
  - id: clean-prompting-notes
    content: 清理 prompting.py 中 SHARED_TOOL_NOTES 和 get_graphiti_supplement 的 agent 相关引用（agent_building_guide、AutoPilotBlock、sub-agent、agent runs）
    status: pending
  - id: prune-tool-registry
    content: 在 tools/__init__.py 中注释掉 16 个 agent 专用工具注册及其 import 语句（create_agent、edit_agent、run_agent、find_agent 等）
    status: pending
  - id: verify-and-test
    content: 验证所有修改文件语法正确，确认 agent 工具不再出现在 TOOL_REGISTRY 中，确保通用工具（bash_exec、web_search、workspace_files 等）正常工作
    status: pending
    dependencies:
      - rewrite-system-prompt
      - disable-builder-context
      - clean-prompting-notes
      - prune-tool-registry
---

## 用户需求

本地 AutoGPT 项目中不需要 agent 相关的自动化功能，希望删除 AI 对 agent 功能的"认知/记忆"，将 copilot 改造为通用 AI 助手。保留其对话、文件操作、搜索等通用能力。

## 核心变更

1. **重写系统提示词**：删除 agent 自动化使命描述，改为通用助手身份
2. **停用 Builder 上下文注入**：不再向 AI 注入 agent 构建指南和图状态
3. **清理工具文档中的 agent 引用**：删除 prompting.py 和 graphiti 指令中的 agent 相关文字
4. **裁剪工具注册表**：注释掉 12+ 个 agent 专用工具，AI 不再感知这些能力
5. **简化服务调用层**：builder_context 函数改为 no-op 后自动生效

## 技术方案

### 实现策略

采用最小侵入策略，只修改 AI 直接"看到"的文本和工具注册表，不改动业务逻辑代码。所有修改点都在 `backend/copilot/` 目录内，前端和数据库无需变更。

### 修改文件清单

| 文件 | 操作 | 说明 |
| --- | --- | --- |
| `service.py` L182-198 | 重写 | 系统提示词：删 agent 使命，删 builder/skills 标签说明 |
| `builder_context.py` L180-258 | 修改 | 两个公开函数改为始终 return "" |
| `prompting.py` L211-230, L570-603 | 修剪 | 删除 agent_building_guide、AutoPilotBlock、sub-agent、agent runs 等引用 |
| `tools/__init__.py` L68-138 | 裁剪 | 注释 16 个 agent 工具注册 + 对应 import |


### 关键设计决策

- **builder_context 函数保留签名**：只改返回逻辑（始终 return ""），不删函数也不删调用点。调用点 `baseline/service.py` 和 `sdk/service.py` 无需修改，编译和测试不受影响。
- **工具注册用注释而非删除**：方便日后恢复。注释掉的工具条目保留原文，加上 `# [AGENT-REMOVED]` 标记。
- **系统提示词从 Langfuse 优先**：`_build_system_prompt()` 优先读 Langfuse 远程配置；当 Langfuse 不可用时才使用 `_CACHEABLE_SYSTEM_PROMPT` 本地回退。如果生产环境使用 Langfuse，需同步修改远程配置。
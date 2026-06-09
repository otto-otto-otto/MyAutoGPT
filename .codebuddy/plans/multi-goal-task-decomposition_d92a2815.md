---
name: multi-goal-task-decomposition
overview: 在系统提示词和工具文档中加入中文语义优化的多目标任务拆解规则，使 AI 能够自动识别复合请求、拆解为独立子任务、处理中文歧义。
todos:
  - id: inject-decomposition-rules
    content: 在 service.py 系统提示词中插入中文多目标拆解规则块：包含触发条件（中文连接词识别）、拆解流程（歧义检测→目标提取→依赖排序→TodoWrite落盘）、TodoWrite规范
    status: completed
  - id: expand-task-notes
    content: 扩展 prompting.py 中 Complex multi-step work 小节：加入中文连接词映射表、歧义检测清单、澄清话术模板、TodoWrite 使用约束
    status: completed
  - id: verify-prompt-consistency
    content: 验证两处修改语法正确且内容互补无冲突，确认系统提示词不超过 token 预算
    status: completed
    dependencies:
      - inject-decomposition-rules
      - expand-task-notes
---

## 用户需求

在 Copilot 系统中注入中文多目标任务拆解能力，使 AI 能够：

1. 自动识别包含多个目标的复合中文句子，分解为有序子任务并使用 TodoWrite 追踪
2. 对指代不明等歧义进行主动澄清，避免在歧义状态下执行错误操作

## 核心功能

- **多目标识别**：识别中文复合句中的并列、顺承、因果、条件等语义关系，提取独立子目标
- **任务编排**：将识别出的子目标按依赖关系和执行优先级排序，生成 pending → in_progress → completed 流转计划
- **歧义消解**：检测代指不明（"这个""那个""他"）、范围模糊（"相关文件""那些东西"）、条件缺失等歧义，在拆解前主动向用户追问
- **TodoWrite 驱动**：拆解结果自动写入 TodoWrite 清单，用户在界面直接看到任务拆解结构和进度

## 技术方案

### 实现策略

纯提示词层面实现——在系统提示词中注入中文任务拆解规则，在工具文档中补充操作指南。无需新增代码、工具或数据库变更。

### 修改文件清单

| 文件 | 插入位置 | 操作 |
| --- | --- | --- |
| `service.py` | L190 之后（"Be concise..." 行后） | 插入「中文多目标拆解」规则块 |
| `prompting.py` | L211-212（替换"Complex multi-step work"小节） | 扩展为中文语义优化的完整任务编排指南 |


### 插入内容设计

#### 1. 系统提示词规则块（`service.py` L190 后插入）

核心规则包含三部分：

- **触发条件**：识别中文连接词（然后、同时、顺便、还有、另外、接着、之后、最后）+ 隐式多目标（无连接词的多句复合）
- **拆解流程**：① 歧义检测 → ② 目标提取 → ③ 依赖排序 → ④ TodoWrite 落盘
- **TodoWrite 规范**：content 用中文祈使句、activeForm 用"正在..."进行时、每轮汇报进度

#### 2. 工具文档指南（`prompting.py` L211-212 替换）

扩展原有的单句指导为包含以下内容的小节：

- 中文连接词映射表（然后=顺序、同时=并行、顺便=低优先级附加、先…再…=硬依赖）
- 歧义检测清单（代词回指、量词模糊、对象缺失、隐含假设）
- 澄清话术模板（"你提到的「X」是指...还是...？"）
- TodoWrite 用法约束（3+ 独立步骤时启用、单向流转 pending→in_progress→completed）

### 关键设计决策

- **规则放在系统提示词而非工具文档**：系统提示词是模型最先读取的顶级指令，多目标拆解属于行为准则而非工具使用技巧，放在系统提示词中模型执行更稳定
- **拆解规则 vs 执行规则分离**：识别/拆解/歧义处理规则放在系统提示词，TodoWrite 操作规范放在工具文档，职责清晰
- **中文优先、英文兼容**：规则描述使用中文连接词和示例，但不排除英文场景，提升通用性
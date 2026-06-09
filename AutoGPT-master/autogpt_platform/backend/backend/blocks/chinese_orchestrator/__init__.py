"""
Chinese-optimized task orchestration module.

Provides Chinese semantic analysis, task decomposition with ambiguity
resolution, and optimized prompt templates for Chinese-context
task execution.
"""

from backend.blocks.chinese_orchestrator.decomposer import (
    ChineseSubTask,
    ChineseTaskDecomposer,
)
from backend.blocks.chinese_orchestrator.prompts import (
    CHINESE_AMBIGUITY_RESOLUTION_PROMPT,
    CHINESE_CONTEXT_SYSTEM_PROMPT,
    CHINESE_SEARCH_UNDERSTANDING_PROMPT,
    CHINESE_TASK_DECOMPOSITION_PROMPT,
    get_chinese_optimized_prompt,
)

__all__ = [
    "ChineseSubTask",
    "ChineseTaskDecomposer",
    "CHINESE_TASK_DECOMPOSITION_PROMPT",
    "CHINESE_AMBIGUITY_RESOLUTION_PROMPT",
    "CHINESE_SEARCH_UNDERSTANDING_PROMPT",
    "CHINESE_CONTEXT_SYSTEM_PROMPT",
    "get_chinese_optimized_prompt",
]

"""Chinese Task Decomposer — semantic analysis & ambiguity resolution.

Provides Chinese text segmentation, multi-word disambiguation, subject
completion, and pronoun resolution.  Used by the Orchestrator block to
improve task decomposition quality for Chinese-language input.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ChineseSubTask:
    """A single decomposed sub-task with ambiguity resolution metadata."""

    id: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    action_type: str = "search"  # search | analyze | generate | execute | verify
    ambiguity_resolved: str = ""
    original_tokens: list[str] = field(default_factory=list)
    estimated_complexity: str = "medium"


@dataclass
class AmbiguityResult:
    """Result of Chinese ambiguity analysis."""

    multi_sense_words: list[dict[str, Any]] = field(default_factory=list)
    missing_subjects: list[dict[str, str]] = field(default_factory=list)
    pronoun_resolution: list[dict[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Chinese text processing utilities
# ---------------------------------------------------------------------------

# Common Chinese multi-sense words with their possible meanings
# Used for rule-based disambiguation before LLM-based analysis
_CHINESE_AMBIGUITY_DICT: dict[str, list[str]] = {
    "苹果": ["苹果公司（Apple Inc.）", "水果苹果"],
    "小米": ["小米公司（Xiaomi）", "谷物小米"],
    "华为": ["华为技术有限公司", "中华有为（成语）"],
    "百度": ["百度公司（Baidu）", "温度计量单位"],
    "阿里": ["阿里巴巴集团", "阿里巴巴（故事人物）"],
    "京东": ["京东集团（JD.com）", "东京（日本首都旧称）"],
    "头条": ["今日头条（字节跳动产品）", "新闻头条"],
    "抖音": ["抖音短视频平台", "音乐节奏"],
    "微信": ["微信（WeChat）", "微小信任"],
    "淘宝": ["淘宝网（电商平台）", "寻找宝物"],
    "美团": ["美团（生活服务平台）", "美丽团体"],
    "滴滴": ["滴滴出行", "水声拟声词"],
    "快手": ["快手短视频平台", "动作敏捷"],
    "火山": ["火山引擎（字节跳动技术品牌）", "地质火山"],
    "云": ["云计算", "气象云朵"],
    "大数据": ["大数据技术", "大量数据"],
    "AI": ["人工智能（Artificial Intelligence）", "Adobe Illustrator"],
    "NLP": ["自然语言处理", "神经语言程序学"],
    "CV": ["计算机视觉", "个人简历"],
    "ML": ["机器学习", "毫升（milliliter）"],
    "DL": ["深度学习", "下载（download）"],
    "API": ["应用程序接口", "美国石油学会"],
    "server": ["服务器", "服务员"],
    "client": ["客户端", "客户"],
    "host": ["主机", "主持人/主人"],
    "driver": ["驱动程序", "司机"],
    "bug": ["程序错误", "虫子"],
    "root": ["根权限（超级用户）", "根/根源"],
    "shell": ["命令行解释器", "外壳"],
    "kernel": ["操作系统内核", "果仁/核心"],
}

# Action-type keyword mapping for Chinese task classification
_ACTION_TYPE_PATTERNS: dict[str, list[str]] = {
    "search": ["搜索", "查找", "查询", "检索", "寻找", "百度", "搜狗", "谷歌", "bing"],
    "analyze": ["分析", "理解", "解读", "评估", "判断", "检查", "比较", "对比"],
    "generate": ["生成", "创建", "编写", "撰写", "制作", "构建", "开发", "设计"],
    "execute": ["执行", "运行", "计算", "处理", "转换", "安装", "配置"],
    "verify": ["验证", "测试", "确认", "检查", "审核", "审查", "校对"],
}


# ---------------------------------------------------------------------------
# Chinese Task Decomposer
# ---------------------------------------------------------------------------


class ChineseTaskDecomposer:
    """Chinese semantic task decomposition and ambiguity resolution.

    Uses a combination of:
    1. Rule-based keyword matching for known ambiguities
    2. jieba segmentation for token extraction
    3. Context-based heuristics for subject completion
    4. Pronoun resolution via pattern matching

    Designed to be used as a pre-processing step before LLM-based
    decomposition in the Orchestrator block.
    """

    def __init__(self):
        self._jieba_available = False
        try:
            import jieba  # noqa: F401
            self._jieba_available = True
        except ImportError:
            logger.info("jieba not installed — using character-based fallback")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def segment(self, text: str) -> list[str]:
        """Segment Chinese text into tokens.

        Uses jieba if available, otherwise falls back to character-based
        segmentation with bigram extraction.
        """
        if self._jieba_available:
            return self._jieba_segment(text)
        return self._char_bigram_segment(text)

    def resolve_ambiguity(self, text: str, context: dict[str, Any] | None = None) -> AmbiguityResult:
        """Analyze and resolve ambiguity in Chinese text.

        Args:
            text: The Chinese text to analyze.
            context: Optional context dict (previous turns, user profile, etc.).

        Returns:
            AmbiguityResult with resolved ambiguities.
        """
        result = AmbiguityResult()

        # 1. Multi-sense word disambiguation
        result.multi_sense_words = self._resolve_multi_sense(text, context or {})

        # 2. Missing subject detection
        result.missing_subjects = self._resolve_missing_subjects(text)

        # 3. Pronoun resolution
        result.pronoun_resolution = self._resolve_pronouns(text, context or {})

        return result

    def decompose(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> list[ChineseSubTask]:
        """Decompose a Chinese task into ordered sub-tasks.

        Applies ambiguity resolution, then uses keyword-based action
        classification to break the task into executable sub-tasks.

        Args:
            task: The Chinese task description.
            context: Optional context for ambiguity resolution.

        Returns:
            Ordered list of ChineseSubTask objects.
        """
        ctx = context or {}

        # Resolve ambiguities first
        ambiguity = self.resolve_ambiguity(task, ctx)

        # Build disambiguated text by replacing ambiguous words
        disambiguated = self._apply_disambiguation(task, ambiguity)

        # Tokenize
        tokens = self.segment(disambiguated)

        # Detect action boundaries using sentence-level splitting
        subtasks = self._split_into_subtasks(disambiguated, tokens)

        # Classify each subtask by action type
        for st in subtasks:
            st.action_type = self._classify_action(st.description)
            st.original_tokens = self.segment(st.description)
            # Store the first resolved ambiguity for traceability
            if ambiguity.multi_sense_words:
                st.ambiguity_resolved = "; ".join(
                    f'{w["word"]}→{w["resolved"]}'
                    for w in ambiguity.multi_sense_words[:3]
                )

        return subtasks

    def build_dag(self, subtasks: list[ChineseSubTask]) -> dict[str, Any]:
        """Build a DAG representation from a list of sub-tasks.

        Returns a dict suitable for graph execution:
        {
            "nodes": [{"id": "task_1", "description": "...", "action": "search"}, ...],
            "edges": [{"from": "task_1", "to": "task_3"}, ...]
        }
        """
        nodes = []
        for st in subtasks:
            nodes.append({
                "id": st.id,
                "description": st.description,
                "action_type": st.action_type,
                "dependencies": st.dependencies,
                "estimated_complexity": st.estimated_complexity,
                "ambiguity_resolved": st.ambiguity_resolved,
            })

        edges = []
        for st in subtasks:
            for dep_id in st.dependencies:
                edges.append({"from": dep_id, "to": st.id})

        return {"nodes": nodes, "edges": edges}

    # ------------------------------------------------------------------
    # Segmentation
    # ------------------------------------------------------------------

    @staticmethod
    def _jieba_segment(text: str) -> list[str]:
        """Segment using jieba (requires jieba installation)."""
        import jieba
        return list(jieba.cut(text))

    @staticmethod
    def _char_bigram_segment(text: str) -> list[str]:
        """Character-level bigram fallback for tokenization."""
        tokens: list[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            if "\u4e00" <= ch <= "\u9fff":  # CJK
                tokens.append(ch)
                if i + 1 < len(text) and "\u4e00" <= text[i + 1] <= "\u9fff":
                    # Don't form bigrams during token extraction —
                    # bigrams will be formed by the caller if needed
                    pass
                i += 1
            elif ch.isalpha():
                start = i
                while i < len(text) and text[i].isalpha():
                    i += 1
                tokens.append(text[start:i])
            elif ch.isdigit():
                start = i
                while i < len(text) and text[i].isdigit():
                    i += 1
                tokens.append(text[start:i])
            else:
                i += 1
        return tokens

    # ------------------------------------------------------------------
    # Ambiguity resolution
    # ------------------------------------------------------------------

    def _resolve_multi_sense(
        self, text: str, context: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Identify and resolve multi-sense (polysemous) words."""
        results = []
        for word, meanings in _CHINESE_AMBIGUITY_DICT.items():
            if word in text:
                # Heuristic: if context contains tech-related terms, prefer
                # the first (usually tech) meaning
                tech_indicators = context.get("domain_keywords", []) + [
                    "技术", "科技", "开发", "编程", "代码", "算法",
                    "AI", "API", "软件", "数据", "云", "搜索", "引擎",
                ]
                is_tech_context = any(kw in text for kw in tech_indicators)

                results.append({
                    "word": word,
                    "possible_meanings": meanings,
                    "resolved": meanings[0] if is_tech_context else meanings[-1],
                    "reason": (
                        "技术语境匹配第一个含义" if is_tech_context
                        else "通用语境匹配最后一个含义"
                    ),
                    "confidence": 0.85 if is_tech_context else 0.6,
                })
        return results

    @staticmethod
    def _resolve_missing_subjects(text: str) -> list[dict[str, str]]:
        """Detect sentences missing an explicit subject.

        Chinese often omits the subject when it's clear from context.
        A sentence starting with a verb (action word) without a
        preceding subject noun likely has a missing subject.
        """
        results = []
        # Split into sentences
        sentences = re.split(r"[。！？；\n]+", text)
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            first_token = sent[:4]  # Check first 1-2 CJK chars
            # If sentence starts with a verb-like word, subject may be missing
            verb_starts = ["请", "帮", "做", "查", "搜", "写", "编", "分析", "整理"]
            if any(first_token.startswith(v) for v in verb_starts):
                results.append({
                    "position": f"句子开头: '{sent[:20]}...'",
                    "resolved_subject": "根据上下文推断的主语（需LLM确认）",
                })
        return results

    @staticmethod
    def _resolve_pronouns(
        text: str, context: dict[str, Any]
    ) -> list[dict[str, str]]:
        """Resolve pronoun references.

        Chinese pronouns: 它(它), 它们(them), 这(this), 那(that),
        这个(this one), 那个(that one), 这些(these), 那些(those).
        """
        pronouns = ["它", "它们", "这", "那", "这个", "那个", "这些", "那些"]
        results = []
        for pronoun in pronouns:
            if pronoun in text:
                # Try to find the antecedent — the most recent noun phrase
                # before the pronoun
                antecedent = context.get("last_topic", "") or "需要LLM推断的指代对象"
                results.append({
                    "pronoun": pronoun,
                    "refers_to": antecedent,
                    "position": text.find(pronoun),
                })
        return results

    # ------------------------------------------------------------------
    # Task decomposition helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_disambiguation(
        text: str, ambiguity: AmbiguityResult
    ) -> str:
        """Replace ambiguous words with their resolved meanings in the text.

        Annotates the text inline with [word→resolved] markers so the
        LLM can see the disambiguation decisions.
        """
        result = text
        for item in ambiguity.multi_sense_words:
            word = item["word"]
            resolved = item["resolved"]
            result = result.replace(word, f"{word}({resolved})")
        return result

    @staticmethod
    def _split_into_subtasks(
        text: str, tokens: list[str]
    ) -> list[ChineseSubTask]:
        """Split text into sub-tasks using sentence boundaries and conjunctions.

        Conjunctions like 然后/接着/并且/同时/另外 indicate sub-task boundaries.
        Sequential actions (先...再...) also indicate dependencies.
        """
        # Split on Chinese sentence separators and task boundary markers
        separators = r"[。！？；\n]+|然后|接着|并且|同时|另外|此外"
        raw_parts = re.split(f"({separators})", text)
        clean_parts = [p.strip() for p in raw_parts if p.strip() and not re.fullmatch(separators, p.strip())]

        if len(clean_parts) <= 1:
            return [
                ChineseSubTask(
                    id="task_1",
                    description=text.strip(),
                    dependencies=[],
                    action_type="search",
                )
            ]

        subtasks = []
        for i, part in enumerate(clean_parts):
            # Determine dependencies: sequential parts depend on earlier ones
            deps = [f"task_{j}" for j in range(1, i)] if i > 0 else []
            subtasks.append(
                ChineseSubTask(
                    id=f"task_{i + 1}",
                    description=part,
                    dependencies=deps,
                )
            )

        return subtasks

    @classmethod
    def _classify_action(cls, description: str) -> str:
        """Classify a sub-task description by its action type."""
        for action_type, keywords in _ACTION_TYPE_PATTERNS.items():
            if any(kw in description for kw in keywords):
                return action_type
        return "search"  # Default: search for information

    @staticmethod
    def estimate_complexity(description: str) -> str:
        """Estimate the complexity of a task based on length and keywords."""
        # Simple heuristic: longer descriptions + certain action types
        # indicate higher complexity
        length = len(description)
        if length < 20:
            return "simple"
        if length > 80:
            return "complex"
        # Check for complex indicators
        complex_indicators = ["分析", "综合", "评估", "比较", "设计", "优化"]
        for indicator in complex_indicators:
            if indicator in description:
                return "complex"
        return "medium"

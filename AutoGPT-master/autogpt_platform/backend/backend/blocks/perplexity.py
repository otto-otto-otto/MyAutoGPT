# flake8: noqa: E501
"""PerplexityBlock — AI-powered search Q&A, now backed by DeepSeek.

Previously used Perplexity Sonar models via OpenRouter.
Now uses DeepSeek's OpenAI-compatible API directly, with results
optionally enriched by Baidu search scraping.
"""

import logging
from enum import Enum
from typing import Any, Literal

import openai

from backend.blocks._base import (
    Block,
    BlockCategory,
    BlockOutput,
    BlockSchemaInput,
    BlockSchemaOutput,
)
from backend.data.model import (
    APIKeyCredentials,
    CredentialsField,
    CredentialsMetaInput,
    NodeExecutionStats,
    SchemaField,
)
from backend.integrations.providers import ProviderName
from backend.util.logging import TruncatedLogger
from backend.util.settings import Settings

logger = TruncatedLogger(logging.getLogger(__name__), "[Perplexity-Block]")

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


class PerplexityModel(str, Enum):
    """Perplexity model identifiers — kept for ``block_cost_config.py`` import.

    The block no longer dispatches on model; all requests use ``deepseek-chat``
    via the DeepSeek API.
    """

    SONAR = "perplexity/sonar"
    SONAR_PRO = "perplexity/sonar-pro"
    SONAR_DEEP_RESEARCH = "perplexity/sonar-deep-research"


PerplexityCredentials = CredentialsMetaInput[
    Literal[ProviderName.OPEN_ROUTER], Literal["api_key"]
]


def PerplexityCredentialsField() -> PerplexityCredentials:
    return CredentialsField(
        description="(Deprecated) Not used — reads DEEPSEEK_API_KEY from env.",
    )


# Optional: enrich search with AI-powered answers
_SEARCH_SYSTEM_PROMPT = (
    "You are a helpful search assistant. "
    "Answer the user's question concisely based on your knowledge and any "
    "provided search results. If search results are provided, cite them. "
    "If search results are not available, answer based on your training data "
    "and note that information may not be up-to-date. "
    "Reply in the same language as the user's query."
)


class PerplexityBlock(Block):
    """AI-powered question answering with optional web search enrichment.

    This block now uses DeepSeek's OpenAI-compatible API as the LLM backend
    instead of Perplexity/OpenRouter.  If search enrichment data is provided
    via the ``search_context`` input, it is injected into the prompt so the
    LLM can cite sources.  Otherwise the LLM answers from its training data.

    Existing agent graphs using the original ``PerplexityBlock`` continue to
    work without requiring OpenRouter credentials — the block reads
    ``DEEPSEEK_API_KEY`` from the platform environment.
    """

    class Input(BlockSchemaInput):
        prompt: str = SchemaField(
            description="The question or query to answer.",
            placeholder="Enter your question here...",
        )
        # Kept for backward compat — old agent graphs may still set this.
        # The block ignores it and always uses deepseek-chat via DeepSeek API.
        model: str = SchemaField(
            title="Model",
            default=DEFAULT_MODEL,
            description="(Ignored) Always uses deepseek-chat via DeepSeek API.",
            advanced=True,
        )
        search_context: str = SchemaField(
            default="",
            description="Optional: raw text from Baidu/Sogou search results "
            "to enrich the LLM answer with real-time data.",
            advanced=True,
        )
        system_prompt: str = SchemaField(
            title="System Prompt",
            default="",
            description="Optional system prompt override.",
            advanced=True,
        )
        max_tokens: int | None = SchemaField(
            advanced=True,
            default=None,
            description="Maximum number of tokens to generate.",
        )
        credentials: PerplexityCredentials = SchemaField(
            default=PerplexityCredentialsField(),
            description="(Deprecated) Not used — reads DEEPSEEK_API_KEY from env.",
            advanced=True,
        )

    class Output(BlockSchemaOutput):
        response: str = SchemaField(
            description="The AI-generated answer."
        )
        annotations: list[dict[str, Any]] = SchemaField(
            description="List of source citations (empty when no search_context provided)."
        )
        error: str = SchemaField(
            description="Error message if the call fails."
        )

    def __init__(self):
        super().__init__(
            id="c8a5f2e9-8b3d-4a7e-9f6c-1d5e3c9b7a4f",
            description="AI智能问答：基于 DeepSeek 大模型回答用户问题，可结合搜索结果为回答提供引用来源。",
            categories={BlockCategory.AI, BlockCategory.SEARCH},
            input_schema=PerplexityBlock.Input,
            output_schema=PerplexityBlock.Output,
            test_input={"prompt": "今天天气怎么样？"},
            test_output=[
                ("response", "根据当前数据，今天天气晴转多云..."),
                ("annotations", []),
            ],
        )
        self.execution_stats = NodeExecutionStats()

    async def run(
        self, input_data: Input, *, credentials: APIKeyCredentials, **kwargs
    ) -> BlockOutput:
        prompt = input_data.prompt.strip()
        if not prompt:
            yield "error", "问题不能为空"
            return

        # Build system prompt
        sys_prompt = input_data.system_prompt or _SEARCH_SYSTEM_PROMPT

        # Build messages
        messages: list[dict[str, str]] = [
            {"role": "system", "content": sys_prompt},
        ]

        # Inject search context if provided
        user_content = prompt
        if input_data.search_context:
            user_content = (
                f"Below are recent web search results related to the query. "
                f"Use them to provide an accurate, up-to-date answer and "
                f"cite the sources.\n\n"
                f"=== SEARCH RESULTS ===\n"
                f"{input_data.search_context}\n"
                f"=== END SEARCH RESULTS ===\n\n"
                f"Question: {prompt}"
            )
        messages.append({"role": "user", "content": user_content})

        api_key = _get_deepseek_api_key()
        if not api_key:
            yield "error", "DEEPSEEK_API_KEY 未配置，请在 .env 中设置"
            return

        client = openai.AsyncOpenAI(
            base_url=DEEPSEEK_BASE_URL,
            api_key=api_key,
            timeout=120.0,
            max_retries=1,
        )

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                max_tokens=input_data.max_tokens,
            )

            if not response.choices:
                raise ValueError("DeepSeek returned no choices")

            content = response.choices[0].message.content or ""

            # Track token usage
            self.execution_stats.input_token_count = 0
            self.execution_stats.output_token_count = 0
            if response.usage:
                self.execution_stats.input_token_count = (
                    response.usage.prompt_tokens or 0
                )
                self.execution_stats.output_token_count = (
                    response.usage.completion_tokens or 0
                )

            yield "response", content
            yield "annotations", []

        except Exception as e:
            logger.error(f"DeepSeek call failed: {e}")
            yield "error", f"AI 调用失败: {e}"


def _get_deepseek_api_key() -> str:
    """Read DeepSeek API key from platform settings."""
    try:
        return Settings().secrets.deepseek_api_key
    except Exception:
        return ""

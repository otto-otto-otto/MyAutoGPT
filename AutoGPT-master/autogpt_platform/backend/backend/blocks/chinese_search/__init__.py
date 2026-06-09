"""
Chinese search engine blocks for Baidu, Sogou, and result aggregation.

Provides native Chinese-language web search capabilities through Baidu
and Sogou search engines, with a cross-engine aggregator that deduplicates
and reranks results using simhash and TF-IDF semantic scoring.
"""

from backend.blocks.chinese_search.aggregator import ChineseSearchAggregatorBlock
from backend.blocks.chinese_search.baidu_search import BaiduSearchBlock
from backend.blocks.chinese_search.sogou_search import SogouSearchBlock

__all__ = [
    "BaiduSearchBlock",
    "ChineseSearchAggregatorBlock",
    "SogouSearchBlock",
]

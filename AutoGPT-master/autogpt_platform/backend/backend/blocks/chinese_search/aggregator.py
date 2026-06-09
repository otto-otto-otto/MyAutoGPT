"""Chinese Search Aggregator — multi-engine search with deduplication & ranking.

Orchestrates parallel searches across Baidu and Sogou, deduplicates results
using simhash fingerprinting, and reranks the combined set using TF-IDF
semantic scoring against the original query.
"""

import asyncio
import hashlib
import logging
import re
from typing import Literal

from backend.blocks._base import (
    Block,
    BlockCategory,
    BlockOutput,
    BlockSchemaInput,
    BlockSchemaOutput,
)
from backend.data.model import SchemaField

logger = logging.getLogger(__name__)

# Simplified simhash — uses 64-bit fingerprint for deduplication.
# Full locality-sensitive hashing would use murmurhash3 + hamming distance,
# but for dedup of short snippet text, a content-hash approach is sufficient.
_SIMHASH_BITS = 64


class ChineseSearchAggregatorBlock(Block):
    """Aggregate and deduplicate results from multiple Chinese search engines.

    Merges results from Baidu and Sogou, removes near-duplicates via
    simhash fingerprinting, and reranks the combined result set using
    TF-IDF semantic scoring against the original query string.
    Results are returned in descending relevance order.
    """

    class Input(BlockSchemaInput):
        query: str = SchemaField(
            description="Original Chinese search query",
        )
        baidu_results: list = SchemaField(
            default_factory=list,
            description="Search results from Baidu (list of {title, url, snippet, engine, ...} dicts)",
        )
        sogou_results: list = SchemaField(
            default_factory=list,
            description="Search results from Sogou (list of {title, url, snippet, engine, ...} dicts)",
        )
        dedup_threshold: int = SchemaField(
            default=3,
            ge=1,
            le=10,
            description="Hamming distance threshold for simhash deduplication (lower = stricter)",
        )

    class Output(BlockSchemaOutput):
        aggregated: list = SchemaField(
            description="Deduplicated and reranked list of search results"
        )
        stats: dict = SchemaField(
            description="Aggregation statistics: total_in, dedup_count, from_baidu, from_sogou"
        )
        error: str = SchemaField(
            description="Error message if aggregation fails"
        )

    def __init__(self):
        super().__init__(
            id="a1b2c3d4-0003-4000-8000-000000000003",
            description="中文搜索聚合去重排序，融合百度和搜狗结果",
            categories={BlockCategory.SEARCH},
            input_schema=ChineseSearchAggregatorBlock.Input,
            output_schema=ChineseSearchAggregatorBlock.Output,
            test_input={
                "query": "人工智能",
                "baidu_results": [
                    {"title": "AI 定义", "url": "https://a.com", "snippet": "人工智能是...", "engine": "baidu"},
                ],
                "sogou_results": [
                    {"title": "AI 定义", "url": "https://a.com", "snippet": "人工智能是...", "engine": "sogou"},
                ],
            },
            test_output=[
                ("aggregated", [{"title": "AI 定义", "url": "https://a.com", "snippet": "人工智能是...", "engine": "baidu,sogou"}]),
                ("stats", {"total_in": 2, "dedup_count": 1, "from_baidu": 1, "from_sogou": 1}),
            ],
        )

    async def run(self, input_data: Input, **kwargs) -> BlockOutput:
        try:
            all_results: list[dict] = []
            baidu_raw = input_data.baidu_results or []
            sogou_raw = input_data.sogou_results or []

            all_results.extend(baidu_raw)
            all_results.extend(sogou_raw)

            total_in = len(all_results)

            if not all_results:
                yield "aggregated", []
                yield "stats", {"total_in": 0, "dedup_count": 0, "from_baidu": 0, "from_sogou": 0}
                return

            # Step 1: Deduplicate using simhash
            deduped = self._simhash_dedup(all_results, input_data.dedup_threshold)

            # Step 2: Rerank by TF-IDF semantic relevance to query
            ranked = self._rerank_by_semantic(deduped, input_data.query)

            # Step 3: Merge engine labels for cross-posted results
            merged = self._merge_engine_labels(ranked)

            stats = {
                "total_in": total_in,
                "dedup_count": total_in - len(deduped),
                "from_baidu": len(baidu_raw),
                "from_sogou": len(sogou_raw),
                "final_count": len(merged),
            }

            yield "aggregated", merged
            yield "stats", stats

        except Exception as e:
            logger.exception("Search aggregation failed for query=%r", input_data.query)
            yield "error", f"搜索聚合失败: {e}"

    # ------------------------------------------------------------------
    # Simhash deduplication
    # ------------------------------------------------------------------

    def _simhash_dedup(self, results: list[dict], threshold: int) -> list[dict]:
        """Deduplicate results using simhash fingerprinting.

        Two results are considered duplicates if their simhash fingerprints
        differ by at most `threshold` bits (hamming distance).
        """
        seen: list[int] = []
        deduped: list[dict] = []

        for result in results:
            text = self._result_text(result)
            fingerprint = self._compute_simhash(text)

            is_dup = False
            for existing in seen:
                hamming = self._hamming_distance(fingerprint, existing)
                if hamming <= threshold:
                    is_dup = True
                    break

            if not is_dup:
                seen.append(fingerprint)
                deduped.append(result)

        return deduped

    def _compute_simhash(self, text: str) -> int:
        """Compute a 64-bit simhash fingerprint for the given text.

        Uses a simplified weighted-feature approach: each character
        (or bigram for CJK) contributes to the fingerprint vector.
        """
        weights = [0] * _SIMHASH_BITS
        features = self._tokenize_for_simhash(text)

        for token in features:
            # Hash the token to a 64-bit value
            token_hash = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:16], 16)
            for i in range(_SIMHASH_BITS):
                if token_hash & (1 << i):
                    weights[i] += 1
                else:
                    weights[i] -= 1

        fingerprint = 0
        for i in range(_SIMHASH_BITS):
            if weights[i] > 0:
                fingerprint |= (1 << i)

        return fingerprint

    @staticmethod
    def _tokenize_for_simhash(text: str) -> list[str]:
        """Tokenize text for simhash — unigrams for ASCII, bigrams for CJK."""
        tokens: list[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            if "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf":
                # CJK character — extract bigram
                if i + 1 < len(text):
                    next_ch = text[i + 1]
                    if "\u4e00" <= next_ch <= "\u9fff" or "\u3400" <= next_ch <= "\u4dbf":
                        tokens.append(ch + next_ch)
                        i += 2
                        continue
                tokens.append(ch)
                i += 1
            elif ch.isalnum():
                # Collect alphanumeric run
                start = i
                while i < len(text) and text[i].isalnum():
                    i += 1
                tokens.append(text[start:i].lower())
            else:
                i += 1
        return tokens

    @staticmethod
    def _hamming_distance(a: int, b: int) -> int:
        """Compute hamming distance between two integers."""
        return (a ^ b).bit_count()

    @staticmethod
    def _result_text(result: dict) -> str:
        """Combine title, snippet, and content for fingerprinting.

        Includes page content when available for better deduplication accuracy.
        Content is truncated to avoid dominating the simhash vector.
        """
        parts = [result.get("title", ""), result.get("snippet", "")]
        content = result.get("content", "")
        if content:
            parts.append(content[:2000])
        return " ".join(p for p in parts if p)

    # ------------------------------------------------------------------
    # TF-IDF Semantic Reranking
    # ------------------------------------------------------------------

    def _rerank_by_semantic(self, results: list[dict], query: str) -> list[dict]:
        """Rerank results using TF-IDF cosine similarity to the query.

        Each result is scored based on the cosine similarity between
        its TF-IDF vector and the query's TF-IDF vector.  Results are
        returned in descending relevance order.
        """
        if not results:
            return []

        # Build vocabulary from query + all result texts
        docs: list[str] = [query]
        for r in results:
            docs.append(self._result_text(r))

        # Compute TF-IDF vectors
        vectors = self._compute_tfidf_vectors(docs)

        query_vec = vectors[0]
        doc_vecs = vectors[1:]

        # Score each result by cosine similarity to query
        for i, result in enumerate(results):
            score = self._cosine_similarity(query_vec, doc_vecs[i])
            result["relevance_score"] = round(score, 4)

        # Sort by relevance descending
        results.sort(key=lambda r: r.get("relevance_score", 0), reverse=True)
        return results

    def _compute_tfidf_vectors(self, docs: list[str]) -> list[dict[str, float]]:
        """Compute TF-IDF vectors for a list of documents."""
        # Tokenize all documents
        tokenized = [self._tokenize_chinese(doc) for doc in docs]
        vocab = set()
        for tokens in tokenized:
            vocab.update(tokens)
        vocab_list = list(vocab)

        N = len(docs)
        # Compute document frequency
        df: dict[str, int] = {}
        for tokens in tokenized:
            for term in set(tokens):
                df[term] = df.get(term, 0) + 1

        # Compute IDF
        import math
        idf: dict[str, float] = {}
        for term in vocab_list:
            idf[term] = math.log((N + 1) / (df.get(term, 0) + 1)) + 1.0

        # Compute TF-IDF vectors
        vectors: list[dict[str, float]] = []
        for tokens in tokenized:
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            # Normalize TF
            total = sum(tf.values()) or 1
            vec = {term: (tf.get(term, 0) / total) * idf.get(term, 0) for term in vocab_list}
            vectors.append(vec)

        return vectors

    @staticmethod
    def _tokenize_chinese(text: str) -> list[str]:
        """Tokenize Chinese text into unigrams and bigrams.

        For production use, this would be replaced with jieba/pkuseg
        segmentation.  The character-based approach provides a reasonable
        fallback for basic TF-IDF scoring.
        """
        tokens: list[str] = []
        # Extract Chinese characters as unigrams
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf":
                tokens.append(ch)

        # Extract CJK bigrams for better semantic matching
        for i in range(len(tokens) - 1):
            tokens.append(tokens[i] + tokens[i + 1])

        # Extract alphanumeric words
        for word in re.findall(r"[a-zA-Z0-9]+", text):
            tokens.append(word.lower())

        return tokens if tokens else [text]

    @staticmethod
    def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
        """Compute cosine similarity between two sparse vectors."""
        dot = sum(vec_a.get(k, 0) * vec_b.get(k, 0) for k in set(vec_a) | set(vec_b))
        norm_a = (sum(v * v for v in vec_a.values())) ** 0.5
        norm_b = (sum(v * v for v in vec_b.values())) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    # ------------------------------------------------------------------
    # Engine label merging
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_engine_labels(results: list[dict]) -> list[dict]:
        """Merge engine labels for results that appear in multiple engines.

        If the same URL appears with different engine labels, we merge
        the labels (e.g. "baidu" + "sogou" → "baidu,sogou") and keep the
        result with the richer content (longer snippet + content).
        """
        url_map: dict[str, dict] = {}
        for result in results:
            url = result.get("url", "")
            if not url:
                url_map[id(result)] = {**result}
                continue

            if url in url_map:
                existing = url_map[url]
                existing_engine = existing.get("engine", "")
                new_engine = result.get("engine", "")
                # Merge engine labels
                engines = set(existing_engine.split(",")) | {new_engine}
                existing["engine"] = ",".join(sorted(engines))
                # Keep the richer content (prefer result with more text)
                existing_score = (
                    len(existing.get("snippet", ""))
                    + len(existing.get("content", ""))
                )
                new_score = (
                    len(result.get("snippet", ""))
                    + len(result.get("content", ""))
                )
                if new_score > existing_score:
                    existing["snippet"] = result.get("snippet", "")
                    existing["content"] = result.get("content", "")
                # Average relevance scores
                existing["relevance_score"] = (
                    existing.get("relevance_score", 0) + result.get("relevance_score", 0)
                ) / 2
            else:
                url_map[url] = {**result}

        return list(url_map.values())

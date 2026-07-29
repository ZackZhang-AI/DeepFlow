"""Embedding provider wrappers for the local knowledge base."""

import hashlib
import math
import re
from http import HTTPStatus
from functools import lru_cache

from cli.config import Config


class EmbeddingError(RuntimeError):
    pass


def _usable_api_key(value: str) -> bool:
    lowered = (value or "").strip().lower()
    placeholder_markers = ("your-", "your_", "replace", "changeme", "example", "sk-your")
    return bool(lowered) and not any(marker in lowered for marker in placeholder_markers)


class LocalHashEmbeddingService:
    """Zero-cost deterministic embedding fallback for the local demo."""

    dimensions = 512

    def embed_documents(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        tokens = _local_tokens(text)
        vector = [0.0] * self.dimensions
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            return [value / norm for value in vector]
        return vector


def _local_tokens(text: str) -> list[str]:
    normalized = text.lower()
    latin = re.findall(r"[a-z0-9_]+", normalized)
    chinese = re.findall(r"[\u4e00-\u9fff]", normalized)
    chinese_bigrams = [
        "".join(chinese[index : index + 2])
        for index in range(max(0, len(chinese) - 1))
    ]
    return latin + chinese + chinese_bigrams


class DashScopeEmbeddingService:
    def __init__(self) -> None:
        if not Config.DASHSCOPE_API_KEY:
            raise EmbeddingError("DASHSCOPE_API_KEY is required for knowledge base embeddings")
        try:
            import dashscope
            from dashscope import TextEmbedding
        except ImportError as exc:
            raise EmbeddingError("dashscope package is required for knowledge base embeddings") from exc

        dashscope.api_key = Config.DASHSCOPE_API_KEY
        self._client = TextEmbedding
        self._api_key = Config.DASHSCOPE_API_KEY
        self._model = Config.EMBEDDING_MODEL

    def embed_documents(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        if not texts:
            return []

        embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = self._client.call(
                model=self._model,
                input=batch,
                api_key=self._api_key,
            )
            if resp.status_code != HTTPStatus.OK:
                message = getattr(resp, "message", "unknown embedding error")
                raise EmbeddingError(f"DashScope embedding failed: {message}")
            embeddings.extend(item["embedding"] for item in resp.output["embeddings"])

        if len(embeddings) != len(texts):
            raise EmbeddingError("Embedding count does not match input text count")
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_documents([text])
        return vectors[0] if vectors else []


class DashScopeRerankService:
    def __init__(self) -> None:
        if not Config.DASHSCOPE_API_KEY:
            raise EmbeddingError("DASHSCOPE_API_KEY is required for knowledge base rerank")
        try:
            import dashscope
            from dashscope import TextReRank
        except ImportError as exc:
            raise EmbeddingError("dashscope package is required for knowledge base rerank") from exc

        dashscope.api_key = Config.DASHSCOPE_API_KEY
        self._client = TextReRank
        self._api_key = Config.DASHSCOPE_API_KEY
        self._model = Config.KB_RERANK_MODEL

    def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        if not documents:
            return []
        resp = self._client.call(
            model=self._model,
            query=query,
            documents=documents,
            top_n=top_n,
            api_key=self._api_key,
        )
        if resp.status_code != HTTPStatus.OK:
            message = getattr(resp, "message", "unknown rerank error")
            raise EmbeddingError(f"DashScope rerank failed: {message}")

        ranked: list[tuple[int, float]] = []
        for item in resp.output.results:
            ranked.append((int(item.index), float(item.relevance_score)))
        return ranked


@lru_cache(maxsize=1)
def get_embedding_service() -> DashScopeEmbeddingService | LocalHashEmbeddingService:
    provider = Config.EMBEDDING_PROVIDER.strip().lower()
    if provider not in {"auto", "local", "dashscope"}:
        raise EmbeddingError(f"Unsupported EMBEDDING_PROVIDER: {provider}")
    if provider == "local" or (provider == "auto" and not _usable_api_key(Config.DASHSCOPE_API_KEY)):
        return LocalHashEmbeddingService()
    return DashScopeEmbeddingService()


@lru_cache(maxsize=1)
def get_rerank_service() -> DashScopeRerankService:
    return DashScopeRerankService()

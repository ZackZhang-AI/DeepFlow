"""Embedding provider wrappers for the local knowledge base."""

from http import HTTPStatus
from functools import lru_cache

from cli.config import Config


class EmbeddingError(RuntimeError):
    pass


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
def get_embedding_service() -> DashScopeEmbeddingService:
    return DashScopeEmbeddingService()


@lru_cache(maxsize=1)
def get_rerank_service() -> DashScopeRerankService:
    return DashScopeRerankService()

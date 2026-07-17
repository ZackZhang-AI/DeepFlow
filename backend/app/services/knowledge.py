"""Lightweight SQLite-backed RAG service for private knowledge."""

from __future__ import annotations

import io
import json
import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from pypdf import PdfReader

from backend.app.core.db import (
    get_knowledge_document,
    list_embedded_knowledge_chunks,
    replace_knowledge_chunks,
    save_knowledge_document,
    update_knowledge_document,
)
from backend.app.services.embedding import EmbeddingError, get_embedding_service, get_rerank_service
from cli.config import Config

MAX_DOCUMENT_CHARS = 300_000
EMBEDDING_BATCH_SIZE = 16
SEPARATORS = ["\n\n", "\n", "\u3002", "\uff1b", ";", ".", " ", ""]


@dataclass
class ParsedDocument:
    title: str
    content: str
    source_name: str
    source_type: str
    pages: list[tuple[int, str]]
    metadata: dict


def ingest_text_document(
    title: str,
    content: str,
    source_name: str = "",
    source_type: str = "text",
    doc_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    doc_id = doc_id or f"doc_{uuid.uuid4().hex[:12]}"
    parsed = ParsedDocument(
        title=title,
        content=content[:MAX_DOCUMENT_CHARS],
        source_name=source_name,
        source_type=source_type,
        pages=[(1, content[:MAX_DOCUMENT_CHARS])],
        metadata={"ingest_mode": "text"},
    )
    return _ingest_parsed_document(parsed, doc_id, user_id=user_id)


def _ingest_parsed_document(parsed: ParsedDocument, doc_id: str, user_id: str | None = None) -> dict:
    content = parsed.content[:MAX_DOCUMENT_CHARS]
    doc = save_knowledge_document(
        doc_id=doc_id,
        title=parsed.title,
        content=content,
        source_name=parsed.source_name,
        source_type=parsed.source_type,
        status="processing",
        metadata=parsed.metadata,
        user_id=user_id or "local_default_user",
    )
    try:
        _embed_and_store(
            doc_id=doc_id,
            title=parsed.title,
            source_name=parsed.source_name,
            source_type=parsed.source_type,
            pages=parsed.pages,
            metadata=parsed.metadata,
            user_id=user_id,
        )
        return get_knowledge_document(doc_id) or doc
    except Exception as exc:
        update_knowledge_document(doc_id, owner_user_id=user_id, status="failed", error_message=str(exc), chunk_count=0)
        raise


def ingest_uploaded_document(filename: str, raw: bytes, user_id: str | None = None) -> dict:
    parsed = parse_uploaded_document(filename, raw)
    return _ingest_parsed_document(parsed, f"doc_{uuid.uuid4().hex[:12]}", user_id=user_id)


def reindex_document(doc_id: str, user_id: str | None = None) -> dict:
    doc = get_knowledge_document(doc_id, user_id=user_id)
    if not doc:
        raise ValueError("Document not found")

    metadata = _loads_json(doc.get("metadata_json"), {})
    parsed = ParsedDocument(
        title=doc["title"],
        content=(doc.get("content") or "")[:MAX_DOCUMENT_CHARS],
        source_name=doc.get("source_name") or "",
        source_type=doc.get("source_type") or "text",
        pages=_pages_from_stored_content(doc.get("content") or ""),
        metadata={**metadata, "reindexed": True},
    )

    update_knowledge_document(doc_id, owner_user_id=user_id, status="processing", error_message="", chunk_count=0)
    try:
        _embed_and_store(
            doc_id=doc_id,
            title=parsed.title,
            source_name=parsed.source_name,
            source_type=parsed.source_type,
            pages=parsed.pages,
            metadata=parsed.metadata,
            user_id=user_id,
        )
    except Exception as exc:
        update_knowledge_document(doc_id, owner_user_id=user_id, status="failed", error_message=str(exc), chunk_count=0)
        raise
    return get_knowledge_document(doc_id, user_id=user_id) or doc


def parse_uploaded_document(filename: str, raw: bytes) -> ParsedDocument:
    if not raw:
        raise ValueError("File is empty")

    suffix = Path(filename or "").suffix.lower()
    title = Path(filename or "knowledge").stem
    if suffix in ("", ".txt", ".md", ".markdown"):
        content = raw.decode("utf-8", errors="replace")[:MAX_DOCUMENT_CHARS]
        return ParsedDocument(
            title=title,
            content=content,
            source_name=filename or "",
            source_type="text",
            pages=[(1, content)],
            metadata={"file_type": suffix.lstrip(".") or "text"},
        )
    if suffix == ".pdf":
        pages = _extract_pdf_pages(raw)
        content = "\n\n".join(f"[Page {page}] {text}" for page, text in pages)[:MAX_DOCUMENT_CHARS]
        return ParsedDocument(
            title=title,
            content=content,
            source_name=filename or "",
            source_type="pdf",
            pages=_trim_pages_to_limit(pages, MAX_DOCUMENT_CHARS),
            metadata={"file_type": "pdf", "page_count": len(pages)},
        )
    raise ValueError("Only txt/md/pdf files are supported")


def search_knowledge_chunks(
    query: str,
    limit: int | None = None,
    score_threshold: float | None = None,
    use_rerank: bool | None = None,
    user_id: str | None = None,
) -> list[dict]:
    query = query.strip()
    if not query:
        return []

    embedding = get_embedding_service().embed_query(query)
    if not embedding:
        return []

    rows = list_embedded_knowledge_chunks(user_id=user_id)
    limit = limit or Config.KNOWLEDGE_TOP_K
    candidate_limit = max(Config.KNOWLEDGE_CANDIDATE_K, limit)
    score_threshold = Config.KNOWLEDGE_SCORE_THRESHOLD if score_threshold is None else score_threshold
    use_rerank = Config.ENABLE_KB_RERANK if use_rerank is None else use_rerank

    query_vec = np.array(embedding, dtype=np.float32)
    query_terms = _tokenize(query)
    raw_results: list[dict] = []
    for row in rows:
        try:
            chunk_vec = np.array(json.loads(row["embedding_json"]), dtype=np.float32)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        vector_score = _cosine_similarity(query_vec, chunk_vec)
        if math.isnan(vector_score):
            continue
        item = dict(row)
        item["vector_score"] = float(vector_score)
        item["keyword_score"] = _keyword_score(query_terms, item["content"])
        item["metadata"] = _loads_json(item.get("metadata_json"), {})
        raw_results.append(item)

    _normalize_scores(raw_results, "vector_score")
    _normalize_scores(raw_results, "keyword_score")

    vector_weight = Config.KNOWLEDGE_VECTOR_WEIGHT
    keyword_weight = Config.KNOWLEDGE_KEYWORD_WEIGHT
    weight_total = vector_weight + keyword_weight
    if weight_total <= 0:
        vector_weight, keyword_weight, weight_total = 1.0, 0.0, 1.0

    results: list[dict] = []
    for item in raw_results:
        hybrid_score = (
            item["vector_score_norm"] * vector_weight
            + item["keyword_score_norm"] * keyword_weight
        ) / weight_total
        item["score"] = float(hybrid_score)
        item["retrieval_mode"] = "hybrid"
        item["rerank_score"] = None
        item["preview"] = item["content"][:800]
        if item["score"] >= score_threshold:
            results.append(item)

    results.sort(key=lambda item: item["score"], reverse=True)
    candidates = results[:candidate_limit]

    if use_rerank and candidates:
        try:
            ranked = get_rerank_service().rerank(
                query=query,
                documents=[item["content"] for item in candidates],
                top_n=min(Config.KB_RERANK_TOP_N, limit),
            )
            reranked: list[dict] = []
            for candidate_index, rerank_score in ranked:
                if candidate_index >= len(candidates):
                    continue
                item = candidates[candidate_index]
                item["rerank_score"] = rerank_score
                item["score"] = rerank_score
                item["retrieval_mode"] = "hybrid_rerank"
                reranked.append(item)
            if reranked:
                return reranked[:limit]
        except EmbeddingError:
            raise
        except Exception:
            return candidates[:limit]

    return candidates[:limit]


def _embed_and_store(
    doc_id: str,
    title: str,
    source_name: str,
    source_type: str,
    pages: list[tuple[int, str]],
    metadata: dict,
    user_id: str | None = None,
) -> None:
    chunks = split_pages_into_chunks(
        pages=pages,
        doc_id=doc_id,
        source_name=source_name,
        chunk_size=Config.KNOWLEDGE_CHUNK_SIZE,
        chunk_overlap=Config.KNOWLEDGE_CHUNK_OVERLAP,
    )
    if not chunks:
        raise ValueError("No chunks were created from the document")

    texts = [chunk["content"] for chunk in chunks]
    embeddings = get_embedding_service().embed_documents(texts, batch_size=EMBEDDING_BATCH_SIZE)
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding
        chunk["metadata"] = {
            **metadata,
            **chunk.get("metadata", {}),
            "title": title,
            "source_type": source_type,
        }

    replace_knowledge_chunks(doc_id, chunks, user_id=user_id)
    update_knowledge_document(
        doc_id,
        owner_user_id=user_id,
        status="ready",
        chunk_count=len(chunks),
        error_message="",
        metadata=metadata,
    )


def split_pages_into_chunks(
    pages: list[tuple[int, str]],
    doc_id: str,
    source_name: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict]:
    chunks: list[dict] = []
    global_index = 0
    for page_num, text in pages:
        page_parts = _apply_overlap(_recursive_split(text, chunk_size), chunk_overlap, chunk_size)
        for part in page_parts:
            cleaned = part.strip()
            if not cleaned:
                continue
            chunk_id = f"{doc_id}_chunk_{global_index}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "chunk_index": global_index,
                    "content": cleaned,
                    "page_num": page_num,
                    "source_name": source_name,
                    "metadata": {"page": page_num},
                }
            )
            global_index += 1
    return chunks


def _recursive_split(text: str, chunk_size: int, separators: Iterable[str] = SEPARATORS) -> list[str]:
    text = text.strip()
    if len(text) <= chunk_size:
        return [text] if text else []

    separators = list(separators)
    sep = separators[0]
    rest = separators[1:] or [""]
    if sep == "":
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    parts = text.split(sep)
    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current}{sep}{part}" if current else part
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.extend(_recursive_split(current, chunk_size, rest))
        current = part
    if current:
        chunks.extend(_recursive_split(current, chunk_size, rest))
    return chunks


def _apply_overlap(parts: list[str], overlap: int, chunk_size: int) -> list[str]:
    if overlap <= 0 or len(parts) <= 1:
        return parts

    overlapped: list[str] = []
    previous_tail = ""
    for part in parts:
        candidate = f"{previous_tail}\n{part}" if previous_tail else part
        if len(candidate) > chunk_size:
            candidate = candidate[-chunk_size:]
        overlapped.append(candidate)
        previous_tail = part[-overlap:] if len(part) > overlap else part
    return overlapped


def _extract_pdf_pages(raw: bytes) -> list[tuple[int, str]]:
    reader = PdfReader(io.BytesIO(raw))
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages[:80], start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((index, text))
    return pages


def _trim_pages_to_limit(pages: list[tuple[int, str]], char_limit: int) -> list[tuple[int, str]]:
    kept: list[tuple[int, str]] = []
    total = 0
    for page_num, text in pages:
        remaining = char_limit - total
        if remaining <= 0:
            break
        kept_text = text[:remaining]
        kept.append((page_num, kept_text))
        total += len(kept_text)
    return kept


def _pages_from_stored_content(content: str) -> list[tuple[int, str]]:
    content = (content or "")[:MAX_DOCUMENT_CHARS]
    matches = list(re.finditer(r"\[Page (\d+)\]\s*", content))
    if not matches:
        return [(1, content)]

    pages: list[tuple[int, str]] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        page_text = content[start:end].strip()
        if page_text:
            pages.append((int(match.group(1)), page_text))
    return pages or [(1, content)]


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    terms = re.findall(r"[a-z0-9][a-z0-9_\-\.]{1,}|[\u4e00-\u9fff]{2,}", lowered)
    cjk_bigrams: list[str] = []
    for term in terms:
        if re.fullmatch(r"[\u4e00-\u9fff]{2,}", term):
            cjk_bigrams.extend(term[i : i + 2] for i in range(len(term) - 1))
    return terms + cjk_bigrams


def _keyword_score(query_terms: list[str], content: str) -> float:
    if not query_terms:
        return 0.0

    haystack_terms = _tokenize(content)
    if not haystack_terms:
        return 0.0

    counts = Counter(haystack_terms)
    score = 0.0
    unique_query_terms = set(query_terms)
    for term in unique_query_terms:
        tf = counts.get(term, 0)
        if tf:
            score += 1.0 + math.log(tf)
    return score / max(1, len(unique_query_terms))


def _normalize_scores(items: list[dict], key: str) -> None:
    norm_key = f"{key}_norm"
    if not items:
        return
    values = [float(item.get(key) or 0.0) for item in items]
    low = min(values)
    high = max(values)
    if high == low:
        for item in items:
            item[norm_key] = 1.0 if high > 0 else 0.0
        return
    for item in items:
        item[norm_key] = (float(item.get(key) or 0.0) - low) / (high - low)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return float("nan")
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return float("nan")
    return float(np.dot(a, b) / denom)


def _loads_json(value: str | None, default: dict) -> dict:
    if not value:
        return default
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return default
    return loaded if isinstance(loaded, dict) else default

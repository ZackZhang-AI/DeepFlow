"""Knowledge base API with lightweight SQLite vector retrieval."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.app.core.db import (
    delete_knowledge_document,
    get_knowledge_document,
    list_knowledge_chunks,
    list_knowledge_documents,
)
from backend.app.core.auth import require_login
from backend.app.models.schemas import KnowledgeDocumentRequest
from backend.app.services.embedding import EmbeddingError
from backend.app.services.knowledge import (
    ingest_text_document,
    ingest_uploaded_document,
    reindex_document,
    search_knowledge_chunks,
)

router = APIRouter(prefix="/api/knowledge-documents", tags=["knowledge"])


@router.get("")
async def list_documents(limit: int = 50, offset: int = 0, user: dict = Depends(require_login)):
    return [_public_doc(doc) for doc in list_knowledge_documents(limit=limit, offset=offset, user_id=user["user_id"])]


@router.post("")
async def create_document(req: KnowledgeDocumentRequest, user: dict = Depends(require_login)):
    try:
        doc = ingest_text_document(
            title=req.title,
            content=req.content,
            source_name=req.source_name,
            source_type=req.source_type,
            user_id=user["user_id"],
        )
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _public_doc(doc)


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), user: dict = Depends(require_login)):
    raw = await file.read()
    try:
        doc = ingest_uploaded_document(file.filename or "knowledge.txt", raw, user_id=user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _public_doc(doc)


@router.get("/search")
async def search_documents(
    q: str,
    limit: int = 5,
    score_threshold: float | None = None,
    rerank: bool | None = None,
    user: dict = Depends(require_login),
):
    try:
        return [
            _public_chunk(chunk)
            for chunk in search_knowledge_chunks(
                q,
                limit=limit,
                score_threshold=score_threshold,
                use_rerank=rerank,
                user_id=user["user_id"],
            )
        ]
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{doc_id}/chunks")
async def get_document_chunks(doc_id: str, user: dict = Depends(require_login)):
    doc = get_knowledge_document(doc_id, user_id=user["user_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return [_public_chunk(chunk, include_score=False) for chunk in list_knowledge_chunks(doc_id, user_id=user["user_id"])]


@router.post("/{doc_id}/reindex")
async def reindex(doc_id: str, user: dict = Depends(require_login)):
    try:
        doc = reindex_document(doc_id, user_id=user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _public_doc(doc)


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, user: dict = Depends(require_login)):
    if not delete_knowledge_document(doc_id, user_id=user["user_id"]):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True, "doc_id": doc_id}


def _public_doc(doc: dict) -> dict:
    return {
        "doc_id": doc["doc_id"],
        "title": doc["title"],
        "source_name": doc.get("source_name") or "",
        "source_type": doc.get("source_type") or "text",
        "content_length": len(doc.get("content", "")) if "content" in doc else doc.get("content_length", 0),
        "status": doc.get("status") or "pending",
        "chunk_count": doc.get("chunk_count") or 0,
        "error_message": doc.get("error_message") or "",
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
    }


def _public_chunk(chunk: dict, include_score: bool = True) -> dict:
    result = {
        "chunk_id": chunk["chunk_id"],
        "doc_id": chunk["doc_id"],
        "chunk_index": chunk["chunk_index"],
        "title": chunk.get("title") or "",
        "source_name": chunk.get("source_name") or "",
        "source_type": chunk.get("source_type") or "",
        "page_num": chunk.get("page_num"),
        "preview": chunk.get("preview") or (chunk.get("content") or "")[:800],
        "content": chunk.get("content") or "",
        "metadata": chunk.get("metadata") or {},
    }
    if include_score:
        result["score"] = chunk.get("score", 0.0)
        result["vector_score"] = chunk.get("vector_score", 0.0)
        result["keyword_score"] = chunk.get("keyword_score", 0.0)
        result["rerank_score"] = chunk.get("rerank_score")
        result["retrieval_mode"] = chunk.get("retrieval_mode") or "stored"
    else:
        result["score"] = 0.0
        result["vector_score"] = 0.0
        result["keyword_score"] = 0.0
        result["rerank_score"] = None
        result["retrieval_mode"] = "stored"
    return result

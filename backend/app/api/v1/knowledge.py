import asyncio
import logging
import os
import tempfile

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from sqlalchemy import delete as sa_delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session_factory
from app.core.exceptions import NotFoundException
from app.core.security import get_current_user
from app.models.knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.models.user import User
from app.rag.engine import RAGEngine
from app.schemas.common import ApiResponse, PageResponse
from app.schemas.knowledge import (
    DocumentResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    SearchResultItem,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])
logger = logging.getLogger(__name__)


def _kb_to_response(
    kb: KnowledgeBase,
    document_count: int = 0,
    total_size: int = 0,
) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        id=str(kb.id),
        name=kb.name,
        description=kb.description,
        embedding_model=kb.embedding_model,
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap,
        status=kb.status,
        config=kb.config or {},
        document_count=document_count,
        total_size=total_size,
        created_at=kb.created_at.isoformat(),
        updated_at=kb.updated_at.isoformat(),
    )


def _doc_to_response(doc: KnowledgeDocument) -> DocumentResponse:
    return DocumentResponse(
        id=str(doc.id),
        knowledge_base_id=str(doc.knowledge_base_id),
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        chunk_count=doc.chunk_count,
        storage_key=doc.storage_key,
        error_message=doc.error_message,
        created_at=doc.created_at.isoformat(),
    )


async def _assert_kb_owned(
    kb_id: str,
    db: AsyncSession,
    tenant_id,
) -> None:
    """Raise NotFoundException if kb_id is not owned by the given tenant.

    Multi-tenant safety net for all /{kb_id}/... sub-routes — without this,
    one tenant could enumerate or modify another tenant's documents by guessing
    a KB UUID.
    """
    if tenant_id is None:
        raise NotFoundException(message="Knowledge base not found")
    result = await db.execute(
        select(KnowledgeBase.id).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == tenant_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundException(message="Knowledge base not found")


@router.post("", response_model=ApiResponse[KnowledgeBaseResponse])
async def create_knowledge_base(
    request: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    kb = KnowledgeBase(
        tenant_id=current_user.tenant_id,
        name=request.name,
        description=request.description,
        embedding_model=request.embedding_model,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
    )
    db.add(kb)
    await db.flush()
    return ApiResponse.success(data=_kb_to_response(kb))


@router.get("", response_model=ApiResponse[PageResponse[KnowledgeBaseResponse]])
async def list_knowledge_bases(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    query = select(KnowledgeBase).where(
        KnowledgeBase.tenant_id == current_user.tenant_id
    )
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        query.offset((page - 1) * size).limit(size).order_by(KnowledgeBase.created_at.desc())
    )
    kb_list = result.scalars().all()

    # Batch query document count and total size per KB
    kb_ids = [kb.id for kb in kb_list]
    doc_stats: dict = {}
    if kb_ids:
        stats_q = (
            select(
                KnowledgeDocument.knowledge_base_id,
                func.count(KnowledgeDocument.id).label("doc_count"),
                func.coalesce(func.sum(KnowledgeDocument.file_size), 0).label("total_size"),
            )
            .where(KnowledgeDocument.knowledge_base_id.in_(kb_ids))
            .group_by(KnowledgeDocument.knowledge_base_id)
        )
        stats_result = await db.execute(stats_q)
        for row in stats_result.all():
            doc_stats[row[0]] = {"doc_count": row[1], "total_size": row[2]}

    items = [
        _kb_to_response(
            kb,
            document_count=doc_stats.get(kb.id, {}).get("doc_count", 0),
            total_size=doc_stats.get(kb.id, {}).get("total_size", 0),
        )
        for kb in kb_list
    ]
    pages = (total + size - 1) // size

    return ApiResponse.success(
        data=PageResponse(items=items, total=total, page=page, size=size, pages=pages)
    )


@router.get("/{kb_id}", response_model=ApiResponse[KnowledgeBaseResponse])
async def get_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise NotFoundException(message="Knowledge base not found")

    stats_q = select(
        func.count(KnowledgeDocument.id).label("doc_count"),
        func.coalesce(func.sum(KnowledgeDocument.file_size), 0).label("total_size"),
    ).where(KnowledgeDocument.knowledge_base_id == kb.id)
    stats_row = (await db.execute(stats_q)).one()

    return ApiResponse.success(
        data=_kb_to_response(kb, document_count=stats_row[0], total_size=stats_row[1])
    )


@router.put("/{kb_id}", response_model=ApiResponse[KnowledgeBaseResponse])
async def update_knowledge_base(
    kb_id: str,
    request: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise NotFoundException(message="Knowledge base not found")

    for field, value in request.dict(exclude_unset=True).items():
        if field == "config":
            # JSONB merge — preserve keys not in incoming update
            merged = dict(kb.config or {})
            merged.update(value or {})
            kb.config = merged
            continue
        setattr(kb, field, value)

    await db.flush()
    return ApiResponse.success(data=_kb_to_response(kb))


@router.delete("/{kb_id}", response_model=ApiResponse)
async def delete_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise NotFoundException(message="Knowledge base not found")

    # Delete documents from MinIO before removing DB records
    doc_result = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.knowledge_base_id == kb.id)
    )
    docs_to_delete = doc_result.scalars().all()
    for doc in docs_to_delete:
        if doc.storage_key:
            try:
                from app.services.storage_service import storage_service
                storage_service.delete_file("documents", doc.storage_key)
            except Exception as e:
                logger.warning("Failed to delete document %s from MinIO: %s", doc.storage_key, e)

    # Cascade delete: chunks -> documents -> knowledge base
    await db.execute(
        sa_delete(KnowledgeChunk).where(KnowledgeChunk.knowledge_base_id == kb.id)
    )
    await db.execute(
        sa_delete(KnowledgeDocument).where(KnowledgeDocument.knowledge_base_id == kb.id)
    )
    await db.delete(kb)
    await db.flush()
    return ApiResponse.success(message="Knowledge base deleted")


async def _run_ingestion(
    knowledge_base_id: str,
    file_path: str,
    filename: str,
    document_id: str,
) -> None:
    """Background task: ingest document using a separate DB session."""
    try:
        async with async_session_factory() as session:
            engine = RAGEngine(session)
            await engine.ingest_document(
                knowledge_base_id=knowledge_base_id,
                file_path=file_path,
                filename=filename,
                document_id=document_id,
            )
    except Exception:
        logger.exception("Background ingestion failed for document %s", document_id)
    finally:
        # Clean up temp file
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except OSError:
            pass


@router.post("/{kb_id}/documents", response_model=ApiResponse[DocumentResponse])
async def upload_document(
    kb_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    # Verify knowledge base exists and belongs to current tenant
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise NotFoundException(message="Knowledge base not found")

    # Determine file type
    file_name = file.filename or "unknown"
    file_type = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "unknown"
    content = await file.read()
    file_size = len(content)

    # Save original file to MinIO (graceful degradation if unavailable)
    storage_key: str | None = None
    try:
        from app.services.storage_service import storage_service
        storage_key = storage_service.upload_file(
            bucket_key="documents",
            file_data=content,
            filename=file_name,
            content_type=file.content_type or "application/octet-stream",
        )
        logger.info("Document saved to MinIO: %s", storage_key)
    except Exception as e:
        logger.warning("MinIO upload failed, continuing without object storage: %s", e)

    # Save file to temp directory
    suffix = f".{file_type}" if file_type != "unknown" else ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=tempfile.gettempdir())
    tmp.write(content)
    tmp.close()
    temp_path = tmp.name

    # Create document record
    doc = KnowledgeDocument(
        knowledge_base_id=kb.id,
        tenant_id=kb.tenant_id,
        filename=file_name,
        file_type=file_type,
        file_size=file_size,
        file_url=temp_path,
        storage_key=storage_key,
        status="processing",
    )
    db.add(doc)
    await db.flush()
    # Commit explicitly so the document record is visible to the background task
    # (which uses a separate DB session).
    await db.commit()

    doc_id = str(doc.id)
    kb_id_str = str(kb.id)

    # Start async ingestion in background
    background_tasks.add_task(
        _run_ingestion,
        knowledge_base_id=kb_id_str,
        file_path=temp_path,
        filename=file_name,
        document_id=doc_id,
    )

    return ApiResponse.success(data=_doc_to_response(doc))


@router.get("/{kb_id}/documents", response_model=ApiResponse[PageResponse[DocumentResponse]])
async def list_documents(
    kb_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    await _assert_kb_owned(kb_id, db, current_user.tenant_id)
    query = select(KnowledgeDocument).where(KnowledgeDocument.knowledge_base_id == kb_id)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        query.offset((page - 1) * size).limit(size).order_by(KnowledgeDocument.created_at.desc())
    )
    items = [_doc_to_response(d) for d in result.scalars().all()]
    pages = (total + size - 1) // size

    return ApiResponse.success(
        data=PageResponse(items=items, total=total, page=page, size=size, pages=pages)
    )


@router.delete("/{kb_id}/documents/{doc_id}", response_model=ApiResponse)
async def delete_document(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    await _assert_kb_owned(kb_id, db, current_user.tenant_id)
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.knowledge_base_id == kb_id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise NotFoundException(message="Document not found")

    # Delete from MinIO if storage_key exists
    if doc.storage_key:
        try:
            from app.services.storage_service import storage_service
            storage_service.delete_file("documents", doc.storage_key)
            logger.info("Deleted document from MinIO: %s", doc.storage_key)
        except Exception as e:
            logger.warning("Failed to delete document from MinIO: %s", e)

    engine = RAGEngine(db)
    await engine.delete_document(doc_id)
    return ApiResponse.success(message="Document deleted")


@router.get("/{kb_id}/documents/{doc_id}/download")
async def download_document(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the original document file from MinIO via presigned URL redirect."""
    from fastapi.responses import RedirectResponse

    await _assert_kb_owned(kb_id, db, current_user.tenant_id)
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.knowledge_base_id == kb_id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise NotFoundException(message="Document not found")

    if not doc.storage_key:
        return ApiResponse.error(code=404, message="原始文件未存储在对象存储中")

    try:
        from app.services.storage_service import storage_service
        url = storage_service.get_presigned_url("documents", doc.storage_key, expires_hours=1)
        return RedirectResponse(url=url)
    except Exception as e:
        logger.error("Failed to generate presigned URL: %s", e)
        return ApiResponse.error(code=500, message=f"获取下载链接失败: {str(e)}")


@router.post("/{kb_id}/search", response_model=ApiResponse[KnowledgeSearchResponse])
async def search_knowledge_base(
    kb_id: str,
    request: KnowledgeSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    # Verify knowledge base exists and belongs to current tenant
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise NotFoundException(message="Knowledge base not found")

    engine = RAGEngine(db)
    search_results = await engine.search(
        knowledge_base_id=kb_id,
        query=request.query,
        top_k=request.top_k,
    )

    items = [
        SearchResultItem(
            chunk_id=r.chunk_id,
            content=r.content,
            similarity=r.similarity,
            chunk_index=r.chunk_index,
            document_id=r.document_id,
        )
        for r in search_results
    ]

    return ApiResponse.success(
        data=KnowledgeSearchResponse(
            query=request.query,
            results=items,
            total=len(items),
        )
    )

"""MinIO object storage service — 对象存储统一服务。

提供文件上传、下载、预签名 URL 和删除功能。
当 MinIO 不可用时优雅降级，不影响核心业务流程。
"""

import io
import logging
import uuid
from datetime import timedelta
from typing import Dict, Optional

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """MinIO object storage service"""

    def __init__(self) -> None:
        self._client: Optional[Minio] = None
        self._initialized: bool = False
        self._buckets: Dict[str, str] = {
            "documents": "bridgeai-documents",       # RAG uploaded files
            "attachments": "bridgeai-attachments",   # Chat file attachments
            "avatars": "bridgeai-avatars",           # Agent/user avatars
            "exports": "bridgeai-exports",           # CSV/report exports
        }

    @property
    def client(self) -> Minio:
        """Lazy-init MinIO client and ensure buckets exist."""
        if self._client is None:
            import urllib3
            # MinIO is local — create a pool manager that does NOT use proxy
            http_client = urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=5, read=10),
                retries=urllib3.Retry(total=1, backoff_factor=0.2),
            )
            self._client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=False,
                http_client=http_client,
            )
        if not self._initialized:
            try:
                for bucket_name in self._buckets.values():
                    if not self._client.bucket_exists(bucket_name):
                        self._client.make_bucket(bucket_name)
                self._initialized = True
            except Exception as e:
                logger.warning("MinIO bucket init failed (will retry): %s", e)
                self._initialized = True  # Don't retry every call
        return self._client

    def upload_file(
        self,
        bucket_key: str,
        file_data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload file to MinIO, returns the object key (path).

        Uses UUID prefix to avoid name collisions.
        """
        bucket = self._buckets[bucket_key]
        object_key = f"{uuid.uuid4().hex[:8]}/{filename}"
        self.client.put_object(
            bucket,
            object_key,
            io.BytesIO(file_data),
            len(file_data),
            content_type=content_type,
        )
        logger.info("Uploaded %s to %s/%s (%d bytes)", filename, bucket, object_key, len(file_data))
        return object_key

    def download_file(self, bucket_key: str, object_key: str) -> bytes:
        """Download file from MinIO."""
        bucket = self._buckets[bucket_key]
        response = self.client.get_object(bucket, object_key)
        try:
            data = response.read()
        finally:
            response.close()
            response.release_conn()
        return data

    def get_presigned_url(
        self,
        bucket_key: str,
        object_key: str,
        expires_hours: int = 1,
    ) -> str:
        """Get a presigned download URL."""
        bucket = self._buckets[bucket_key]
        return self.client.presigned_get_object(
            bucket, object_key, expires=timedelta(hours=expires_hours)
        )

    def delete_file(self, bucket_key: str, object_key: str) -> None:
        """Delete file from MinIO."""
        bucket = self._buckets[bucket_key]
        self.client.remove_object(bucket, object_key)
        logger.info("Deleted %s/%s", bucket, object_key)

    def is_available(self) -> bool:
        """Check if MinIO is reachable."""
        try:
            self.client.list_buckets()
            return True
        except Exception:
            return False


# Global singleton
storage_service = StorageService()

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import aiofiles
from fastapi import UploadFile

from tenderlens.core.errors import AppError

READ_CHUNK_SIZE = 1024 * 1024
PDF_HEADER_SCAN_BYTES = 1024


@dataclass(frozen=True, slots=True)
class StoredUpload:
    document_id: UUID
    path: Path
    original_filename: str
    content_type: str
    sha256: str
    size_bytes: int


class FileSystemDocumentStorage:
    def __init__(self, root: Path, max_upload_size_bytes: int) -> None:
        self.root = root.resolve()
        self.max_upload_size_bytes = max_upload_size_bytes

    async def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def source_path(self, document_id: UUID) -> Path:
        return self.root / str(document_id) / "source.pdf"

    async def save(self, document_id: UUID, upload: UploadFile) -> StoredUpload:
        original_filename = self._safe_filename(upload.filename)
        document_dir = self.root / str(document_id)
        document_dir.mkdir(parents=True, exist_ok=False)
        target = document_dir / "source.pdf"
        digest = hashlib.sha256()
        size_bytes = 0
        header = bytearray()

        try:
            async with aiofiles.open(target, "wb") as output:
                while chunk := await upload.read(READ_CHUNK_SIZE):
                    size_bytes += len(chunk)
                    if size_bytes > self.max_upload_size_bytes:
                        raise AppError(
                            code="document_too_large",
                            message="The PDF exceeds the configured upload limit.",
                            status_code=413,
                            details={"max_bytes": self.max_upload_size_bytes},
                        )
                    if len(header) < PDF_HEADER_SCAN_BYTES:
                        needed = PDF_HEADER_SCAN_BYTES - len(header)
                        header.extend(chunk[:needed])
                    digest.update(chunk)
                    await output.write(chunk)

            if size_bytes == 0 or b"%PDF-" not in header:
                raise AppError(
                    code="invalid_pdf",
                    message="The uploaded file is not a valid PDF.",
                    status_code=415,
                )
        except Exception:
            await self.delete(document_id)
            raise
        finally:
            await upload.close()

        return StoredUpload(
            document_id=document_id,
            path=target,
            original_filename=original_filename,
            content_type=upload.content_type or "application/octet-stream",
            sha256=digest.hexdigest(),
            size_bytes=size_bytes,
        )

    async def delete(self, document_id: UUID) -> None:
        target = self.source_path(document_id)
        if target.exists():
            target.unlink()
        document_dir = target.parent
        if document_dir.exists():
            document_dir.rmdir()

    @staticmethod
    def _safe_filename(filename: str | None) -> str:
        if not filename:
            return "document.pdf"
        normalized = filename.replace("\\", "/")
        name = Path(normalized).name.strip()
        if not name:
            return "document.pdf"
        return name[:255]

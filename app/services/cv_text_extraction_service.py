from dataclasses import dataclass

from app.models.cv import CV, CVSourceType
from app.services.cv_storage_service import CVStorageService
from app.services.document_text_extractor import (
    DocumentStorageError,
    DocumentTextResult,
    UnsupportedDocumentTypeError,
    UploadedDocumentTextExtractor,
)


@dataclass(frozen=True)
class UploadedCVTextSource:
    """Detached storage metadata needed to extract one uploaded CV document."""

    source_type: CVSourceType
    storage_key: str | None
    mime_type: str | None
    original_filename: str | None


class CVTextExtractionService:
    def __init__(
        self,
        storage: CVStorageService | None = None,
        extractor: UploadedDocumentTextExtractor | None = None,
    ) -> None:
        self.storage = storage or CVStorageService()
        self.extractor = extractor or UploadedDocumentTextExtractor()

    def extract_uploaded_cv(
        self, cv: CV | UploadedCVTextSource
    ) -> DocumentTextResult:
        if cv.source_type != CVSourceType.UPLOADED:
            raise UnsupportedDocumentTypeError(
                "CV được tạo bằng Builder không sử dụng trình trích xuất tài liệu."
            )
        try:
            path = self.storage.get_file_path(cv.storage_key)
        except (FileNotFoundError, OSError) as exc:
            raise DocumentStorageError(
                "Không thể đọc tệp CV đã tải lên từ bộ nhớ hệ thống."
            ) from exc
        return self.extractor.extract(path, cv.mime_type, cv.original_filename)

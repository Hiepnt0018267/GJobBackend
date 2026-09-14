from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

import fitz
from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.core.config import settings


class DocumentFileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"


@dataclass(frozen=True)
class DocumentTextResult:
    text: str
    file_type: DocumentFileType
    character_count: int
    page_count: int | None = None


class DocumentExtractionError(RuntimeError):
    """Base error for safe, in-memory document text extraction failures."""


class UnsupportedDocumentTypeError(DocumentExtractionError):
    pass


class EmptyDocumentTextError(DocumentExtractionError):
    pass


class EncryptedDocumentError(DocumentExtractionError):
    pass


class DocumentTextTooLargeError(DocumentExtractionError):
    pass


class DocumentStorageError(DocumentExtractionError):
    pass


class DocumentTextExtractor(Protocol):
    def extract(self, path: Path) -> DocumentTextResult:
        ...


_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\r\n]+")
_EXCESSIVE_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_document_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        character
        for character in text
        if character in {"\n", "\t"} or unicodedata.category(character) != "Cc"
    )
    lines = [_HORIZONTAL_WHITESPACE.sub(" ", line).strip() for line in text.split("\n")]
    return _EXCESSIVE_BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


class _BaseTextExtractor:
    file_type: DocumentFileType
    empty_text_message = "Tài liệu không chứa văn bản có thể trích xuất."

    def __init__(self, max_characters: int | None = None) -> None:
        self.max_characters = (
            max_characters
            if max_characters is not None
            else settings.CV_EXTRACTED_TEXT_MAX_CHARACTERS
        )

    def _result(self, text: str, page_count: int | None = None) -> DocumentTextResult:
        normalized = normalize_document_text(text)
        if not normalized:
            raise EmptyDocumentTextError(self.empty_text_message)
        if len(normalized) > self.max_characters:
            raise DocumentTextTooLargeError(
                "Văn bản trích xuất vượt quá giới hạn an toàn cho phép."
            )
        return DocumentTextResult(
            text=normalized,
            file_type=self.file_type,
            character_count=len(normalized),
            page_count=page_count,
        )


class PDFTextExtractor(_BaseTextExtractor):
    file_type = DocumentFileType.PDF
    empty_text_message = (
        "Không thể trích xuất văn bản từ tài liệu này. OCR chưa được hỗ trợ."
    )

    def extract(self, path: Path) -> DocumentTextResult:
        try:
            with fitz.open(path) as document:
                if document.needs_pass:
                    raise EncryptedDocumentError(
                        "PDF được bảo vệ bằng mật khẩu và không thể trích xuất."
                    )
                text = "\n\n".join(page.get_text("text", sort=True) for page in document)
                return self._result(text, page_count=document.page_count)
        except DocumentExtractionError:
            raise
        except Exception as exc:
            raise DocumentExtractionError(
                "Không thể trích xuất văn bản từ PDF. Tệp có thể đã bị hỏng."
            ) from exc


def _iter_docx_blocks(document):
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


class DOCXTextExtractor(_BaseTextExtractor):
    file_type = DocumentFileType.DOCX

    def extract(self, path: Path) -> DocumentTextResult:
        try:
            document = Document(path)
            blocks: list[str] = []
            for block in _iter_docx_blocks(document):
                if isinstance(block, Paragraph):
                    blocks.append(block.text)
                    continue
                for row in block.rows:
                    cell_values = [
                        " ".join(paragraph.text for paragraph in cell.paragraphs).strip()
                        for cell in row.cells
                    ]
                    blocks.append(" | ".join(value for value in cell_values if value))
            return self._result("\n".join(blocks))
        except DocumentExtractionError:
            raise
        except Exception as exc:
            raise DocumentExtractionError(
                "Không thể trích xuất văn bản từ DOCX. Tệp có thể đã bị hỏng."
            ) from exc


class UploadedDocumentTextExtractor:
    PDF_MIME = "application/pdf"
    DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def __init__(self, max_characters: int | None = None) -> None:
        self._extractors: dict[DocumentFileType, DocumentTextExtractor] = {
            DocumentFileType.PDF: PDFTextExtractor(max_characters),
            DocumentFileType.DOCX: DOCXTextExtractor(max_characters),
        }

    @classmethod
    def _file_type(cls, mime_type: str | None, filename: str | None) -> DocumentFileType:
        normalized_mime = (mime_type or "").split(";", 1)[0].strip().lower()
        extension = Path(filename or "").suffix.lower()
        if normalized_mime == cls.PDF_MIME and extension == ".pdf":
            return DocumentFileType.PDF
        if normalized_mime == cls.DOCX_MIME and extension == ".docx":
            return DocumentFileType.DOCX
        raise UnsupportedDocumentTypeError(
            "Chỉ hỗ trợ trích xuất văn bản từ tệp PDF hoặc DOCX hợp lệ."
        )

    def extract(
        self,
        path: Path,
        mime_type: str | None,
        filename: str | None,
    ) -> DocumentTextResult:
        file_type = self._file_type(mime_type, filename)
        return self._extractors[file_type].extract(path)

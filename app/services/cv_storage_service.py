"""Private storage primitives shared by uploaded CV files and Builder CV photos."""

from __future__ import annotations

import os
import uuid
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath, PureWindowsPath

import pymupdf as fitz
from docx import Document
from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings


class CVFileValidationError(ValueError):
    """Raised when a submitted CV asset does not meet the accepted contract."""


@dataclass(frozen=True)
class StoredCVFile:
    storage_key: str
    original_filename: str
    mime_type: str
    file_size: int


class CVStorageService:
    _CHUNK_SIZE = 1024 * 1024
    _MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
    _MIME_BY_EXTENSION = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    _PHOTO_FORMATS = {
        ".jpg": ("image/jpeg", "JPEG"),
        ".jpeg": ("image/jpeg", "JPEG"),
        ".png": ("image/png", "PNG"),
        ".webp": ("image/webp", "WEBP"),
    }

    def __init__(self, storage_root: str | Path | None = None, max_bytes: int | None = None) -> None:
        self.root = Path(storage_root or settings.CV_UPLOAD_STORAGE_ROOT).resolve()
        self.max_bytes = max_bytes if max_bytes is not None else settings.CV_UPLOAD_MAX_BYTES

    @staticmethod
    def _safe_original_filename(filename: str | None) -> str:
        if not filename:
            raise CVFileValidationError("A file name is required.")
        name = Path(PureWindowsPath(filename).name).name
        if name in {"", ".", ".."}:
            raise CVFileValidationError("Invalid file name.")
        return name[:255]

    def _path_for_key(self, storage_key: str) -> Path:
        key = PurePosixPath(storage_key)
        if key.is_absolute() or ".." in key.parts or key.parts[:1] not in {("cvs",), ("cv-images",), ("cv-template-thumbnails",)}:
            raise FileNotFoundError("Invalid stored CV asset.")
        resolved = (self.root / Path(*key.parts)).resolve()
        if self.root != resolved and self.root not in resolved.parents:
            raise FileNotFoundError("Invalid stored CV asset.")
        return resolved

    @classmethod
    def _validate_declared_type(cls, filename: str, declared_mime: str | None) -> tuple[str, str]:
        extension = Path(filename).suffix.lower()
        expected_mime = cls._MIME_BY_EXTENSION.get(extension)
        if expected_mime is None:
            raise CVFileValidationError("Only PDF and DOCX CV files are accepted.")
        if (declared_mime or "").split(";", 1)[0].strip().lower() != expected_mime:
            raise CVFileValidationError("The file extension and declared content type do not match.")
        return extension, expected_mime

    @staticmethod
    def _validate_pdf(path: Path) -> None:
        with path.open("rb") as file:
            if b"%PDF-" not in file.read(1024):
                raise CVFileValidationError("The uploaded PDF file is invalid.")
        try:
            document = fitz.open(stream=path.read_bytes(), filetype="pdf")
            try:
                if not document.is_pdf:
                    raise CVFileValidationError("The uploaded PDF file is invalid.")
            finally:
                document.close()
        except CVFileValidationError:
            raise
        except Exception as exc:
            raise CVFileValidationError("The uploaded PDF file is invalid.") from exc

    def _validate_docx(self, path: Path) -> None:
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if {"[Content_Types].xml", "word/document.xml"} - names:
                    raise CVFileValidationError("The uploaded DOCX file is invalid.")
                if sum(entry.file_size for entry in archive.infolist()) > self._MAX_DOCX_UNCOMPRESSED_BYTES:
                    raise CVFileValidationError("The uploaded DOCX file is too large after extraction.")
                if archive.testzip() is not None:
                    raise CVFileValidationError("The uploaded DOCX file is invalid.")
            Document(path)
        except CVFileValidationError:
            raise
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            raise CVFileValidationError("The uploaded DOCX file is invalid.") from exc

    async def _write_upload(self, upload: UploadFile, max_bytes: int) -> tuple[Path, int]:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary_root = self.root / ".tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        temporary_path = temporary_root / f"{uuid.uuid4().hex}.upload"
        file_size = 0
        try:
            with temporary_path.open("xb") as destination:
                while chunk := await upload.read(self._CHUNK_SIZE):
                    file_size += len(chunk)
                    if file_size > max_bytes:
                        raise CVFileValidationError("The uploaded file exceeds the allowed size limit.")
                    destination.write(chunk)
            if file_size == 0:
                raise CVFileValidationError("The uploaded file is empty.")
            return temporary_path, file_size
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    async def store_upload(self, candidate_id: uuid.UUID, upload: UploadFile) -> StoredCVFile:
        filename = self._safe_original_filename(upload.filename)
        extension, mime_type = self._validate_declared_type(filename, upload.content_type)
        temporary_path, file_size = await self._write_upload(upload, self.max_bytes)
        try:
            if extension == ".pdf":
                self._validate_pdf(temporary_path)
            else:
                self._validate_docx(temporary_path)
            key = f"cvs/{candidate_id}/{uuid.uuid4()}{extension}"
            path = self._path_for_key(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary_path, path)
            return StoredCVFile(key, filename, mime_type, file_size)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    async def store_photo(self, candidate_id: uuid.UUID, upload: UploadFile) -> str:
        filename = self._safe_original_filename(upload.filename)
        extension = Path(filename).suffix.lower()
        expected = self._PHOTO_FORMATS.get(extension)
        if expected is None:
            await upload.close()
            raise CVFileValidationError("Only JPG, JPEG, PNG, and WEBP images are accepted.")
        declared_mime = (upload.content_type or "").split(";", 1)[0].strip().lower()
        if declared_mime != expected[0]:
            await upload.close()
            raise CVFileValidationError("The image extension and declared content type do not match.")
        temporary_path, _ = await self._write_upload(upload, settings.CV_PHOTO_MAX_BYTES)
        try:
            try:
                with Image.open(temporary_path) as image:
                    image.verify()
                with Image.open(temporary_path) as image:
                    if image.format != expected[1]:
                        raise CVFileValidationError("The image content does not match its file type.")
                    if image.width > settings.CV_PHOTO_MAX_DIMENSION or image.height > settings.CV_PHOTO_MAX_DIMENSION:
                        raise CVFileValidationError("The image dimensions exceed the allowed limit.")
                    normalized = ImageOps.exif_transpose(image).convert("RGB")
                    buffer = BytesIO()
                    normalized.save(buffer, format="WEBP", quality=88, method=6)
            except CVFileValidationError:
                raise
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                raise CVFileValidationError("The uploaded image is invalid.") from exc
            key = f"cv-images/{candidate_id}/{uuid.uuid4()}.webp"
            destination = self._path_for_key(key)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(buffer.getvalue())
            return key
        finally:
            temporary_path.unlink(missing_ok=True)

    async def store_template_thumbnail(self, template_id: uuid.UUID, upload: UploadFile) -> tuple[str, str]:
        filename = self._safe_original_filename(upload.filename)
        extension = Path(filename).suffix.lower()
        expected = self._PHOTO_FORMATS.get(extension)
        if expected is None or (upload.content_type or "").split(";", 1)[0].strip().lower() != expected[0]:
            await upload.close()
            raise CVFileValidationError("Only JPG, JPEG, PNG, and WEBP images are accepted.")
        temporary_path, _ = await self._write_upload(upload, settings.CV_PHOTO_MAX_BYTES)
        try:
            try:
                with Image.open(temporary_path) as image:
                    image.verify()
                with Image.open(temporary_path) as image:
                    if image.format != expected[1] or image.width > settings.CV_PHOTO_MAX_DIMENSION or image.height > settings.CV_PHOTO_MAX_DIMENSION:
                        raise CVFileValidationError("The thumbnail image is invalid or exceeds the allowed dimensions.")
                    normalized = ImageOps.exif_transpose(image).convert("RGB")
                    buffer = BytesIO()
                    normalized.save(buffer, format="WEBP", quality=88, method=6)
            except CVFileValidationError:
                raise
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                raise CVFileValidationError("The uploaded image is invalid.") from exc
            key = f"cv-template-thumbnails/{template_id}/{uuid.uuid4()}.webp"
            destination = self._path_for_key(key)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(buffer.getvalue())
            return key, filename
        finally:
            temporary_path.unlink(missing_ok=True)

    def get_file_path(self, storage_key: str | None) -> Path:
        if not storage_key:
            raise FileNotFoundError("This CV does not have an uploaded file.")
        path = self._path_for_key(storage_key)
        if not path.is_file():
            raise FileNotFoundError("The uploaded CV asset is unavailable.")
        return path

    def delete_file(self, storage_key: str | None) -> None:
        if not storage_key:
            return
        try:
            self._path_for_key(storage_key).unlink(missing_ok=True)
        except FileNotFoundError:
            return

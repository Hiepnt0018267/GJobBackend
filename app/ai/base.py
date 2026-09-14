from typing import Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class AIProvider(Protocol):
    """Contract chuẩn cho mọi AI Provider trong hệ thống GJob."""

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Sinh văn bản từ prompt. Luôn trả về chuỗi text đã được chuẩn hóa."""
        ...

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> object:
        """Generate JSON-compatible data constrained by a Pydantic schema."""
        ...

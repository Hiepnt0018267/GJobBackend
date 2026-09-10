from typing import Protocol, runtime_checkable

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
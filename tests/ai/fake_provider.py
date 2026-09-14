from pydantic import BaseModel

from app.ai.base import AIProvider


class FakeAIProvider(AIProvider):
    def __init__(
        self,
        stub_response: str = "GJOB_GEMINI_OK",
        structured_response: object | None = None,
    ):
        self.stub_response = stub_response
        self.structured_response = structured_response
        self.last_prompt: str | None = None
        self.last_system_instruction: str | None = None
        self.last_response_schema: type[BaseModel] | None = None
        self.last_temperature: float | None = None
        self.call_count: int = 0

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        self.last_prompt = prompt
        self.call_count += 1
        return self.stub_response

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> object:
        self.last_prompt = prompt
        self.last_system_instruction = system_instruction
        self.last_response_schema = response_schema
        self.last_temperature = temperature
        self.call_count += 1
        return self.structured_response

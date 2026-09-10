from app.ai.base import AIProvider

class FakeAIProvider(AIProvider):
    def __init__(self, stub_response: str = "GJOB_GEMINI_OK"):
        self.stub_response = stub_response
        self.last_prompt: str | None = None
        self.call_count: int = 0

    async def generate_text(self, prompt: str, system_instruction: str | None = None, temperature: float = 0.0) -> str:
        self.last_prompt = prompt
        self.call_count += 1
        return self.stub_response
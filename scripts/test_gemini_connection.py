"""Manual-only Gemini connectivity smoke test; never run from pytest."""

from pathlib import Path
import sys
import asyncio

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai.exceptions import AIProviderError
from app.ai.factory import create_ai_provider


async def main() -> None:
    try:
        response = await create_ai_provider().generate_text(
            "Reply with exactly: GJOB_GEMINI_OK"
        )
    except AIProviderError as exc:
        print(f"Gemini connection: FAILED ({type(exc).__name__})")
        raise SystemExit(1) from exc

    print("Gemini connection: OK")
    print("Response:", response)


if __name__ == "__main__":
    asyncio.run(main())
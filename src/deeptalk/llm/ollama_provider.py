from __future__ import annotations

import httpx
from deeptalk.artifacts.models import Citation
from deeptalk.llm.provider import LlmResult


class OllamaProvider:
    """Ollama API client compatible with the LlmProvider protocol.

    Uses Ollama's /api/generate endpoint with a local model for fast,
    lightweight completions.  Perfect for real-time meeting summarization.
    """

    def __init__(
        self,
        url: str = "http://localhost:11434",
        model: str = "llama3.2:3b",
    ) -> None:
        self._url = url.rstrip("/")
        self._model = model

    @property
    def name(self) -> str:
        return "ollama"

    async def _generate(self, prompt: str, system: str | None = None) -> str:
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.2,
            "options": {"num_predict": 1024},
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._url}/api/generate",
                json=payload,
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()

    async def search_answer(self, query: str) -> LlmResult:
        system = "You are a helpful meeting assistant. Answer the question concisely."
        text = await self._generate(query, system=system)
        return LlmResult(text=text, citations=[], model=self._model)

    async def complete(self, prompt: str) -> str:
        return await self._generate(prompt)

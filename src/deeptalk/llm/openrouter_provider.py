from __future__ import annotations

import httpx
from deeptalk.artifacts.models import Citation
from deeptalk.llm.provider import LlmResult


class OpenRouterProvider:
    """OpenRouter API client compatible with the LlmProvider protocol."""

    def __init__(
        self,
        model: str = "google/gemini-2.5-flash",
        api_key: str | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "openrouter"

    async def _post(self, messages: list[dict[str, str]]) -> str:
        if not self._api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/jpliem/deeptalk",
            "X-Title": "DeepTalk",
        }
        payload = {
            "model": self._model,
            "messages": messages,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def search_answer(self, query: str) -> LlmResult:
        # Instruct generic models to act as search answerers.
        system_prompt = (
            "You are a web search assistant. Answer the user's query comprehensively."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        text = await self._post(messages)
        return LlmResult(text=text, citations=[], model=self._model)

    async def complete(self, prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        return await self._post(messages)

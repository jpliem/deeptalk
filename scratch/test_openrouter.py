import os
import asyncio
import httpx
from deeptalk.config import Config
from deeptalk.llm.openrouter_provider import OpenRouterProvider

async def main():
    config = Config.from_env()
    print("Search Provider:", config.search_provider)
    print("OpenRouter Model:", config.openrouter_model)
    print("API Key exists:", bool(config.openrouter_api_key))
    if config.openrouter_api_key:
        print("API Key preview:", config.openrouter_api_key[:10] + "...")
        
    provider = OpenRouterProvider(model=config.openrouter_model, api_key=config.openrouter_api_key)
    try:
        print("Calling search_answer...")
        res = await provider.search_answer("Is Postgres better than SQLite?")
        print("Result:")
        print(res.text[:500])
    except Exception as e:
        print("Error details:")
        print(e)
        if isinstance(e, httpx.HTTPStatusError):
            print("Response text:")
            print(e.response.text)

if __name__ == "__main__":
    asyncio.run(main())

# ============================================================
# agent/llm_factory.py — returns a LangChain ChatOpenAI
#   pointed at whichever provider is configured in .env
#   Swap provider by changing LLM_PROVIDER=gemini|qwen|openai
# ============================================================

from langchain_openai import ChatOpenAI
from config.settings import settings


def get_llm(temperature: float | None = None) -> ChatOpenAI:
    """
    Returns a LangChain ChatOpenAI instance configured for the
    active provider. All providers expose an OpenAI-compatible API.
    """
    return ChatOpenAI(
        model=settings.resolved_model,
        api_key=settings.llm_api_key,
        base_url=settings.resolved_base_url,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        max_tokens=4096,
        timeout=120,
    )

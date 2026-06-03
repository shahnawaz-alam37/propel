# ============================================================
# config/settings.py — all env/config lives here
# ============================================================

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    # ----------------------------------------------------------
    # LLM Provider — swap without touching agent code
    # ----------------------------------------------------------
    # Options: "groq" | "gemini" | "qwen" | "openai" | "codex"
    llm_provider: Literal["groq", "gemini", "qwen", "openai", "codex"] = "gemini"

    # API key for whichever provider you're using
    llm_api_key: str = Field(..., env="LLM_API_KEY")

    # Model name (overridable per provider)
    llm_model: str = Field(default="", env="LLM_MODEL")

    # ----------------------------------------------------------
    # Provider base URLs (OpenAI-compatible endpoints)
    # ----------------------------------------------------------
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    openai_base_url: str = "https://api.openai.com/v1"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    # codex_base_url: str = "..."  # fill when available

    # ----------------------------------------------------------
    # Default models per provider
    # ----------------------------------------------------------
    gemini_default_model: str = "gemini-2.5-flash"
    qwen_default_model: str = "qwen-plus"
    openai_default_model: str = "gpt-4o"
    groq_default_model: str = "qwen/qwen3-32b"

    # ----------------------------------------------------------
    # Compiler service
    # ----------------------------------------------------------
    compiler_url: str = "http://localhost:8001"
    compiler_timeout: int = 90  # seconds

    # ----------------------------------------------------------
    # Agent behaviour
    # ----------------------------------------------------------
    max_compile_retries: int = 3       # how many times to self-fix LaTeX errors
    max_agent_iterations: int = 10
    llm_temperature: float = 0.2       # low = consistent LaTeX output

    # ----------------------------------------------------------
    # App
    # ----------------------------------------------------------
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def resolved_base_url(self) -> str:
        return {
            "groq": self.groq_base_url,
            "gemini": self.gemini_base_url,
            "qwen": self.qwen_base_url,
            "openai": self.openai_base_url,
            "codex": self.openai_base_url,   # adjust when codex ships
        }[self.llm_provider]

    @property
    def resolved_model(self) -> str:
        if self.llm_model:
            return self.llm_model
        return {
            "groq": self.groq_default_model,
            "gemini": self.gemini_default_model,
            "qwen": self.qwen_default_model,
            "openai": self.openai_default_model,
            "codex": "codex-1",
        }[self.llm_provider]


settings = Settings()

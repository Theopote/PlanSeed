"""应用设置 Pydantic 模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from packages.llm.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TIMEOUT_S,
)


class LlmSettings(BaseModel):
    """需求解析 LLM 配置（local-first：仅 ollama / mock）。"""

    provider: Literal["ollama", "mock"] = "ollama"
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    ollama_timeout_s: float = Field(
        default=DEFAULT_OLLAMA_TIMEOUT_S,
        ge=5.0,
        le=600.0,
    )
    ollama_allow_remote: bool = False

    @field_validator("ollama_base_url")
    @classmethod
    def _strip_base_url(cls, value: str) -> str:
        url = value.strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            raise ValueError("ollama_base_url 须以 http:// 或 https:// 开头")
        return url

    @field_validator("ollama_model")
    @classmethod
    def _strip_model(cls, value: str) -> str:
        model = value.strip()
        if not model:
            raise ValueError("ollama_model 不能为空")
        return model


class AppSettings(BaseModel):
    """持久化到 settings.json 的顶层结构。"""

    version: int = 1
    llm: LlmSettings = Field(default_factory=LlmSettings)


class SettingsResponse(BaseModel):
    """GET /api/settings 响应：有效配置 + 元数据。"""

    llm: LlmSettings
    persisted: bool
    settings_path: str
    env_overrides: dict[str, bool] = Field(
        default_factory=dict,
        description="各字段是否被进程环境变量覆盖（未写入 settings.json）",
    )

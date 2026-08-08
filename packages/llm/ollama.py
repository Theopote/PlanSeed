"""OllamaProvider — 唯一允许的本地 LLM HTTP 实现（Phase 6.1）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"
DEFAULT_OLLAMA_TIMEOUT_S = 120.0


class OllamaError(RuntimeError):
    """Ollama 调用失败基类。"""


class OllamaConnectionError(OllamaError):
    """无法连接本地 Ollama。"""


class OllamaHTTPError(OllamaError):
    """Ollama 返回非 2xx。"""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        super().__init__(f"Ollama HTTP {status_code}: {detail}")


class OllamaResponseError(OllamaError):
    """响应体无法解析为 JSON object。"""


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    model: str = DEFAULT_OLLAMA_MODEL
    timeout_s: float = DEFAULT_OLLAMA_TIMEOUT_S
    # "json" 或 JSON Schema dict；None 则不传 format（不推荐）
    response_format: str | dict[str, Any] | None = "json"
    temperature: float | None = 0.1

    def chat_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/chat"

    def tags_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/tags"


class OllamaProvider:
    """
    通过 Ollama `/api/chat` 完成结构化 JSON。

    禁止在本类中调用 solver 或写几何；只返回 dict 供 gate 消费。
    """

    def __init__(
        self,
        config: OllamaConfig | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config or OllamaConfig()
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=self.config.timeout_s)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> OllamaProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def is_available(self) -> bool:
        """探测 `/api/tags`；失败返回 False（不抛）。"""
        try:
            r = self._client.get(self.config.tags_url())
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        if self.config.response_format is not None:
            body["format"] = self.config.response_format
        if self.config.temperature is not None:
            body["options"] = {"temperature": self.config.temperature}

        try:
            response = self._client.post(self.config.chat_url(), json=body)
        except httpx.RequestError as exc:
            raise OllamaConnectionError(
                f"无法连接 Ollama（{self.config.base_url}）：{exc}"
            ) from exc

        if response.status_code >= 400:
            raise OllamaHTTPError(
                response.status_code,
                (response.text or "")[:500],
            )

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise OllamaResponseError(f"Ollama 响应非 JSON：{exc}") from exc

        content = _extract_message_content(payload)
        return _parse_json_object(content)


def _extract_message_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise OllamaResponseError("Ollama 响应须为 object")
    message = payload.get("message")
    if not isinstance(message, dict):
        raise OllamaResponseError("缺少 message 字段")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise OllamaResponseError("message.content 为空或非字符串")
    return content.strip()


def _parse_json_object(content: str) -> dict[str, Any]:
    """解析模型文本；容忍偶发 markdown 围栏。"""
    text = content
    if text.startswith("```"):
        lines = text.splitlines()
        # 去掉首行 ```json 与末行 ```
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OllamaResponseError(f"模型输出不是合法 JSON：{exc}") from exc

    if not isinstance(data, dict):
        raise OllamaResponseError("模型 JSON 必须是 object（LLMRequirementDraft）")
    return data

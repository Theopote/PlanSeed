"""测试 / 离线用 MockLLMProvider（无网络、无 Ollama）。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


class MockLLMProvider:
    """按序返回预设 JSON；耗尽则抛错。"""

    def __init__(
        self,
        responses: Sequence[dict[str, Any]] | Callable[[str, str], dict[str, Any]],
    ) -> None:
        if callable(responses) and not isinstance(responses, Sequence):
            self._fn: Callable[[str, str], dict[str, Any]] | None = responses
            self._queue: list[dict[str, Any]] = []
        else:
            self._fn = None
            self._queue = list(responses)

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        if self._fn is not None:
            return self._fn(system, user)
        if not self._queue:
            raise RuntimeError("MockLLMProvider 响应已耗尽")
        return self._queue.pop(0)

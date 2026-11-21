"""局部重生成作用域错误 — API 映射为 HTTP 422。"""

from __future__ import annotations


class RegenerationScopeError(ValueError):
    """非法 RegenerationScope / base placements / 锁冲突。"""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        room_ids: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.room_ids = list(room_ids or [])
        self.message = message

    def to_detail(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "room_ids": self.room_ids,
        }

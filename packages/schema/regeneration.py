"""局部重生成作用域 — v0.2-B Partial Regeneration。

RegenerationScope 描述「哪些房间可重排、哪些必须钉死」；
实际几何锁由 base candidate + scope 推导为 LayoutLocks。
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class RegenerationScope(BaseModel):
    """
    局部重生成意图（≠ LayoutLocks）。

    - mutable_rooms：允许 Guillotine 重新切分的 program 房间
    - locked_rooms：显式钉死；为空时 = 全部 program 房间 − mutable_rooms
    - affected_neighbors：拓扑邻接、可能受影响的房间（默认可由 solver 推导填充）
    - preserve_topology：意图标记；当前未作为硬不变量验收（勿在 UI 宣称已保证）
    - preserve_floor_assignment：为 True 时校验锁定房间楼层与 program 一致（硬）
    """

    mutable_rooms: list[str] = Field(
        min_length=1,
        description="待重生成/重排的 room_id 列表",
    )
    locked_rooms: list[str] = Field(
        default_factory=list,
        description="显式锁定；空则锁定其余全部 program 房间",
    )
    affected_neighbors: list[str] = Field(
        default_factory=list,
        description="可能受影响的邻接房间；空则由 topology 推导",
    )
    preserve_topology: bool = Field(
        default=True,
        description="拓扑保留意图（尚未硬化为硬不变量；勿对外保证）",
    )
    preserve_floor_assignment: bool = Field(
        default=True,
        description="硬校验：锁定房间 floor_id 须与 DesignProgram 楼层分配一致",
    )

    @model_validator(mode="after")
    def _mutable_locked_disjoint(self) -> RegenerationScope:
        overlap = set(self.mutable_rooms) & set(self.locked_rooms)
        if overlap:
            raise ValueError(f"mutable_rooms 与 locked_rooms 不得重叠：{sorted(overlap)}")
        return self

    @property
    def mutable_room_ids(self) -> set[str]:
        return set(self.mutable_rooms)

    @property
    def locked_room_ids(self) -> set[str]:
        return set(self.locked_rooms)

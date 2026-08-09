"""固定 Top-K（axis）选优回归 fixture。

刻意构造可预测的分池与几何偏移，锁定 Alpha 默认
``rank_mode=axis`` 的角色顺序；改 selection 语义须同步改本期望并 bump selection_version。
"""

from __future__ import annotations

from packages.schema.layout import (
    CandidateValidation,
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.scoring import DesignScore

# 与 SolverConfig / identity 对齐的冻结契约
FIXTURE_ID = "topk-axis-roles-v1"
EXPECTED_SELECTION_VERSION = "axis-diversity-v1"
EXPECTED_RANK_MODE = "axis"
BUILDABLE_WIDTH = 30.0
BUILDABLE_DEPTH = 20.0
TOP_K = 5
MIN_DIVERSITY_THRESHOLD = 0.85

# (candidate_id, selection_role, selection_label) — 顺序即 Top-K 顺序
EXPECTED_TOP_ROLES: tuple[tuple[str, str, str], ...] = (
    ("c-top", "top_score", "最高总分"),
    ("c-circ", "circulation", "流线更好"),
    ("c-priv", "privacy", "隐私更好"),
    ("c-env", "environment", "朝向更好"),
    ("c-fill", "diverse", "几何多样"),
)


def _placement(
    *,
    x: float,
    y: float = 0.0,
    width: float = 5.0,
    depth: float = 4.0,
) -> list[FloorLayout]:
    return [
        FloorLayout(
            floor_id="F1",
            placements=[
                RoomPlacement(
                    room_id="living",
                    floor_id="F1",
                    rect=PlacementRect(x=x, y=y, width=width, depth=depth),
                    source=PlacementSource.PROGRAM,
                    name="客厅",
                    category="public",
                )
            ],
        )
    ]


def _candidate(
    *,
    cid: str,
    seed: int,
    total: float,
    circ: float,
    priv: float,
    env: float,
    x: float,
    y: float = 0.0,
    width: float = 5.0,
    depth: float = 4.0,
) -> LayoutCandidate:
    score = DesignScore(
        total_score=total,
        program_score=total,
        spatial_score=total,
        circulation_score=circ,
        privacy_score=priv,
        environment_score=env,
        technical_score=50.0,
        robustness_score=50.0,
    )
    return LayoutCandidate(
        id=cid,
        seed=seed,
        floors=_placement(x=x, y=y, width=width, depth=depth),
        score=total,
        evaluation=score,
        validation=CandidateValidation(
            valid=True,
            hard_violations=[],
            soft_violations=[],
        ),
        metrics={"fixture_id": FIXTURE_ID},
    )


def axis_topk_role_pool() -> list[LayoutCandidate]:
    """返回冻结候选池（含诱饵，不应进入 Top-5 叙事位）。"""
    return [
        _candidate(
            cid="c-top",
            seed=0,
            total=92.0,
            circ=55.0,
            priv=50.0,
            env=48.0,
            x=0.0,
            y=0.0,
            width=5.0,
            depth=4.0,
        ),
        _candidate(
            cid="c-circ",
            seed=1,
            total=84.0,
            circ=88.0,
            priv=45.0,
            env=40.0,
            x=18.0,
            y=0.0,
            width=8.0,
            depth=3.0,
        ),
        _candidate(
            cid="c-priv",
            seed=2,
            total=83.0,
            circ=50.0,
            priv=86.0,
            env=42.0,
            x=0.0,
            y=12.0,
            width=4.0,
            depth=7.0,
        ),
        _candidate(
            cid="c-env",
            seed=3,
            total=82.0,
            circ=48.0,
            priv=44.0,
            env=90.0,
            x=20.0,
            y=14.0,
            width=6.0,
            depth=5.0,
        ),
        _candidate(
            cid="c-fill",
            seed=4,
            total=81.0,
            circ=52.0,
            priv=51.0,
            env=50.0,
            x=10.0,
            y=8.0,
            width=3.0,
            depth=9.0,
        ),
        # 总分第二但轴优势不足 + 几何贴近 top → 不得抢叙事位
        _candidate(
            cid="c-near-top",
            seed=5,
            total=90.0,
            circ=56.0,
            priv=51.0,
            env=49.0,
            x=0.3,
            y=0.0,
            width=5.0,
            depth=4.0,
        ),
        # 无效候选不得入选
        LayoutCandidate(
            id="c-invalid",
            seed=6,
            floors=_placement(x=3.0),
            score=99.0,
            evaluation=DesignScore(
                total_score=99.0,
                program_score=99.0,
                spatial_score=99.0,
                circulation_score=99.0,
                privacy_score=99.0,
                environment_score=99.0,
                technical_score=99.0,
                robustness_score=99.0,
            ),
            validation=CandidateValidation(
                valid=False,
                hard_violations=[],
                soft_violations=[],
            ),
            metrics={"fixture_id": FIXTURE_ID},
        ),
    ]

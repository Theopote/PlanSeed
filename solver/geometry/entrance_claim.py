"""入口边走廊：提升为门厅或并入公区，避免 ExteriorEntry 落在细条走廊。"""

from __future__ import annotations

from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.program import DesignProgram
from packages.schema.site import CardinalEdge
from solver.circulation.exterior_entry import resolve_entry_edge
from solver.geometry.coverage import (
    LAYOUT_ABSORB_TOLERANCE,
    merge_adjacent_rects,
    try_absorb_sliver_without_overlap,
)
from solver.geometry.exterior import program_exterior_segments
from solver.geometry.rect import from_placement, intersection, shared_edge_length
from solver.geometry.site_coords import SiteCoordinateSystem


def _is_generated_circ(p: RoomPlacement) -> bool:
    if p.room_id.startswith("stair-") or p.room_id.startswith("void-"):
        return False
    if p.room_id.startswith("circ-"):
        return True
    return (p.category or "").lower() == "circulation" and p.name == "走廊"


def _touches_entrance_exterior(
    rect,
    program: DesignProgram,
    entrance_edge: CardinalEdge,
    *,
    min_seg: float = 0.5,
) -> bool:
    cs = SiteCoordinateSystem.from_site(program.site)
    wanted = cs.model_edges_facing(
        entrance_edge.value if hasattr(entrance_edge, "value") else str(entrance_edge)
    )
    for seg in program_exterior_segments(rect, program):
        if seg.direction in wanted and seg.length + 1e-9 >= min_seg:
            return True
    return False


def _promote_circ_to_foyer(p: RoomPlacement, floor_id: str, index: int) -> RoomPlacement:
    return p.model_copy(
        update={
            "room_id": f"foyer-{floor_id}-{index}",
            "name": "门厅",
            "category": "public",
            "source": PlacementSource.GENERATED,
        }
    )


def claim_entrance_edge_circulation(
    candidate: LayoutCandidate,
    program: DesignProgram,
    *,
    min_shared_edge: float = 0.5,
    max_area_by_room_id: dict[str, float] | None = None,
) -> LayoutCandidate:
    """
    一层入口边：选一块够宽的走廊提升为门厅，并吞并相邻入口细条走廊。

    楼梯锁在入口边时，旁侧 residual circ 常抢走 ExteriorEntry；
    提升为 public「门厅」后入口可落在公区。
    """
    del max_area_by_room_id  # 门厅提升不扩 program 房间面积
    if not candidate.floors:
        return candidate
    entrance = resolve_entry_edge(program)
    ground = candidate.floors[0]
    placements = [p.model_copy(deep=True) for p in ground.placements]
    absorb_tol = LAYOUT_ABSORB_TOLERANCE

    # 先把入口发丝走廊按邻接块并入较宽走廊（只删被吞并的部分）
    from solver.geometry.free_rects import subtract_rects

    hair_merged = True
    while hair_merged:
        hair_merged = False
        for i, p in enumerate(placements):
            if not _is_generated_circ(p):
                continue
            hair = from_placement(p.rect)
            if min(hair.width, hair.depth) >= 0.3:
                continue
            if not _touches_entrance_exterior(
                hair, program, entrance, min_seg=0.3
            ):
                continue
            progress = False
            for j, other in enumerate(list(placements)):
                if i == j or not _is_generated_circ(other):
                    continue
                orect = from_placement(other.rect)
                if min(orect.width, orect.depth) < 0.3:
                    continue
                others = [
                    from_placement(placements[k].rect)
                    for k in range(len(placements))
                    if k not in (i, j)
                ]
                merged = try_absorb_sliver_without_overlap(
                    orect, hair, others, tolerance=absorb_tol
                )
                if merged is None:
                    continue
                # 从发丝中减去被并入的部分
                absorbed = intersection(hair, merged)
                if absorbed is None or absorbed.area <= 1e-9:
                    # 整段被拉进邻廊
                    absorbed = hair
                leftovers = subtract_rects([hair], [absorbed])
                placements[j] = other.model_copy(
                    update={
                        "rect": PlacementRect(
                            x=merged.x,
                            y=merged.y,
                            width=merged.width,
                            depth=merged.depth,
                        )
                    }
                )
                if not leftovers:
                    placements.pop(i)
                else:
                    # 保留残余发丝
                    first, *rest = leftovers
                    placements[i] = p.model_copy(
                        update={
                            "rect": PlacementRect(
                                x=first.x,
                                y=first.y,
                                width=first.width,
                                depth=first.depth,
                            )
                        }
                    )
                    for piece in rest:
                        placements.append(
                            p.model_copy(
                                update={
                                    "room_id": f"circ-{ground.floor_id}-hair-{len(placements)}",
                                    "rect": PlacementRect(
                                        x=piece.x,
                                        y=piece.y,
                                        width=piece.width,
                                        depth=piece.depth,
                                    ),
                                }
                            )
                        )
                progress = True
                hair_merged = True
                break
            if progress:
                break

    candidates: list[tuple[float, int]] = []
    for i, p in enumerate(placements):
        if not _is_generated_circ(p):
            continue
        rect = from_placement(p.rect)
        if not _touches_entrance_exterior(rect, program, entrance, min_seg=0.3):
            continue
        short = min(rect.width, rect.depth)
        score = rect.area + min(short, 2.0) * 2.0
        candidates.append((score, i))
    if not candidates:
        return candidate

    candidates.sort(reverse=True)
    foyer_i = candidates[0][1]
    placements[foyer_i] = _promote_circ_to_foyer(
        placements[foyer_i], ground.floor_id, 0
    )

    # 把贴入口的发丝走廊并入门厅
    absorb_tol = LAYOUT_ABSORB_TOLERANCE
    changed = True
    while changed:
        changed = False
        foyer = placements[foyer_i]
        foyer_rect = from_placement(foyer.rect)
        for j, p in enumerate(list(placements)):
            if j == foyer_i or not _is_generated_circ(p):
                continue
            circ_rect = from_placement(p.rect)
            if not _touches_entrance_exterior(
                circ_rect, program, entrance, min_seg=0.3
            ):
                # 也允许与门厅共边的发丝条
                if min(circ_rect.width, circ_rect.depth) >= 0.3:
                    continue
            shared = shared_edge_length(foyer_rect, circ_rect)
            near = shared >= min_shared_edge or (
                min(circ_rect.width, circ_rect.depth) < 0.3
                and shared_edge_length(foyer_rect, circ_rect) >= 0.05
            )
            # 容差：几乎共边
            if not near:
                if abs(foyer_rect.bottom - circ_rect.top) <= absorb_tol or abs(
                    foyer_rect.top - circ_rect.bottom
                ) <= absorb_tol:
                    overlap = min(foyer_rect.right, circ_rect.right) - max(
                        foyer_rect.left, circ_rect.left
                    )
                    near = overlap >= min_shared_edge
                elif abs(foyer_rect.right - circ_rect.left) <= absorb_tol or abs(
                    foyer_rect.left - circ_rect.right
                ) <= absorb_tol:
                    overlap = min(foyer_rect.bottom, circ_rect.bottom) - max(
                        foyer_rect.top, circ_rect.top
                    )
                    near = overlap >= min_shared_edge
            if not near:
                continue
            others = [
                from_placement(placements[k].rect)
                for k in range(len(placements))
                if k not in (foyer_i, j)
            ]
            merged = try_absorb_sliver_without_overlap(
                foyer_rect, circ_rect, others, tolerance=absorb_tol
            )
            if merged is None:
                merged = merge_adjacent_rects(foyer_rect, circ_rect)
                if merged is not None:
                    for other_rect in others:
                        inter = intersection(merged, other_rect)
                        if inter is not None and inter.area > 1e-6:
                            merged = None
                            break
            if merged is None:
                continue
            placements[foyer_i] = foyer.model_copy(
                update={
                    "rect": PlacementRect(
                        x=merged.x,
                        y=merged.y,
                        width=merged.width,
                        depth=merged.depth,
                    )
                }
            )
            placements.pop(j)
            if j < foyer_i:
                foyer_i -= 1
            changed = True
            break

    # 发丝合并可能留下缺口：回填为走廊
    from solver.geometry.buildable import program_pack_rects
    from solver.geometry.coverage import assign_residual_gaps_as_circulation

    pack = program_pack_rects(program)
    placements = assign_residual_gaps_as_circulation(
        pack if pack else from_placement(
            PlacementRect(
                x=0,
                y=0,
                width=program.site.width,
                depth=program.site.depth,
            )
        ),
        placements,
        ground.floor_id,
    )
    # 若回填又产生入口走廊，再提升一次（仅当尚无门厅）
    if not any(p.room_id.startswith("foyer-") for p in placements):
        return candidate
    new_ground = ground.model_copy(update={"placements": placements})
    floors: list[FloorLayout] = [new_ground, *list(candidate.floors[1:])]
    return candidate.model_copy(update={"floors": floors})

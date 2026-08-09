"""Phase 8.3 — CP-SAT assignment research（非整几何替代）。

适用：floor / zone / topology / hard adjacency / orientation eligibility。
禁止：用 CP-SAT 直接输出房间坐标或替换 Guillotine/MaxRect packing。
"""

from solver.assignment.cpsat_floor import (
    CpSatFloorAssigner,
    CpSatFloorAssignError,
    CpSatUnavailableError,
    assign_floors_cpsat,
)

__all__ = [
    "CpSatFloorAssignError",
    "CpSatFloorAssigner",
    "CpSatUnavailableError",
    "assign_floors_cpsat",
]

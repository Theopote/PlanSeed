"""PlanSeed Schema v2 — 前后端、LLM 与 Solver 共用的领域模型。"""

from packages.schema.constraints import (
    AccessConstraint,
    AdjacencyConstraint,
    AlignmentConstraint,
    AreaConstraint,
    Constraint,
    ConstraintKind,
    FloorConstraint,
    OrientationConstraint,
    SeparationConstraint,
    WidthConstraint,
)
from packages.schema.layout import (
    CandidateValidation,
    FloorLayout,
    LayoutCandidate,
    RoomPlacement,
    Violation,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.project import HouseholdSpec, PreferencesSpec, ProjectSpec
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.scoring import DesignMetrics, DesignScore
from packages.schema.site import (
    CardinalEdge,
    CardinalOrientation,
    SetbackSpec,
    SiteSpec,
)

__all__ = [
    "AccessConstraint",
    "AdjacencyConstraint",
    "AlignmentConstraint",
    "AreaConstraint",
    "CandidateValidation",
    "CardinalEdge",
    "CardinalOrientation",
    "Constraint",
    "ConstraintKind",
    "DesignMetrics",
    "DesignProgram",
    "DesignScore",
    "FloorConstraint",
    "FloorLayout",
    "FloorSpec",
    "HouseholdSpec",
    "LayoutCandidate",
    "OrientationConstraint",
    "PreferencesSpec",
    "ProjectSpec",
    "RoomCategory",
    "RoomPlacement",
    "RoomSpec",
    "SeparationConstraint",
    "SetbackSpec",
    "SiteSpec",
    "SolverConfig",
    "Violation",
    "WidthConstraint",
]

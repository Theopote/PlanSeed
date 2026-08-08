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
from packages.schema.entry import ExteriorEntry
from packages.schema.layout import (
    CandidateValidation,
    DoorOpening,
    FloorLayout,
    LayoutCandidate,
    RoomPlacement,
    Violation,
    WetStack,
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
from packages.schema.topology import (
    AccessGraph,
    SpaceConnection,
    SpaceConnectionType,
    TopologyPlan,
)

__all__ = [
    "AccessConstraint",
    "AccessGraph",
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
    "DoorOpening",
    "ExteriorEntry",
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
    "SpaceConnection",
    "SpaceConnectionType",
    "TopologyPlan",
    "Violation",
    "WetStack",
    "WidthConstraint",
]

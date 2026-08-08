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
from packages.schema.entry import (
    ExteriorEntry,
    ExteriorEntryPlacement,
    ExteriorEntrySpec,
)
from packages.schema.layout import (
    CandidateValidation,
    DoorOpening,
    FloorLayout,
    LayoutCandidate,
    RepairRecord,
    RoomPlacement,
    Violation,
    WetStack,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.project import HouseholdSpec, PreferencesSpec, ProjectSpec
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec, SemanticRole
from packages.schema.scoring import (
    DesignEvaluation,
    DesignFinding,
    DesignMetrics,
    DesignScore,
    EvaluationAxis,
    FindingSeverity,
)
from packages.schema.site import (
    CardinalEdge,
    CardinalOrientation,
    SetbackSpec,
    SiteSpec,
)
from packages.schema.topology import (
    AccessGraph,
    ConnectionState,
    RealizedConnection,
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
    "ConnectionState",
    "Constraint",
    "ConstraintKind",
    "DesignEvaluation",
    "DesignFinding",
    "DesignMetrics",
    "DesignProgram",
    "DesignScore",
    "DoorOpening",
    "EvaluationAxis",
    "ExteriorEntry",
    "ExteriorEntryPlacement",
    "ExteriorEntrySpec",
    "FindingSeverity",
    "FloorConstraint",
    "FloorLayout",
    "FloorSpec",
    "HouseholdSpec",
    "LayoutCandidate",
    "OrientationConstraint",
    "PreferencesSpec",
    "ProjectSpec",
    "RealizedConnection",
    "RepairRecord",
    "RoomCategory",
    "RoomPlacement",
    "RoomSpec",
    "SemanticRole",
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

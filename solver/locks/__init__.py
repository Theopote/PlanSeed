"""LayoutLocks 管线契约：校验 + 不变式。"""

from solver.locks.envelopes import (
    build_zone_member_envelopes,
    placement_in_envelope,
    placements_respect_zone_envelopes,
)
from solver.locks.invariants import check_lock_invariants
from solver.locks.validate import (
    LockValidationError,
    LockValidationIssue,
    LockValidationResult,
    assert_valid_layout_locks,
    validate_layout_locks,
)

__all__ = [
    "LockValidationError",
    "LockValidationIssue",
    "LockValidationResult",
    "assert_valid_layout_locks",
    "build_zone_member_envelopes",
    "check_lock_invariants",
    "placement_in_envelope",
    "placements_respect_zone_envelopes",
    "validate_layout_locks",
]

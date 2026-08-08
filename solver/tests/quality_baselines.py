"""
Quality regression 阈值 — Phase 1.5 起开始记录。

原则：
- 阈值应低于当前实测基线，留出算法演进空间
- 但远高于「valid>=1 / distinct>1」这种几乎无意义的门槛
- 收紧阈值前先更新 MEASURED_BASELINE 注释

基准案例：11×13m 两层旧手册户型，candidate_count=32, base_seed=42
实测（2026-08，StairCore + diversity 后）：
  valid_ratio ≈ 0.875 (28/32)
  distinct_layouts = 32
  distinct_valid = 28
  top area_accuracy ≈ 0.8635
  top hard_violations = 0
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityThresholds:
    """可配置质量门槛；测试与 CI 共用。"""

    candidate_count: int = 32
    min_valid_ratio: float = 0.70
    min_distinct_layouts: int = 8
    min_distinct_valid: int = 8
    min_top_area_accuracy: float = 0.70
    min_top_k: int = 5
    require_top_all_valid: bool = True
    min_core_placements: int = 2  # seed 应产生多种楼梯核区位


# 当前仓库默认门槛
DEFAULT_QUALITY = QualityThresholds()

# 记录实测基线（非断言，供人工对照 / 未来收紧）
MEASURED_BASELINE = {
    "date": "2026-08-08",
    "case": "benchmark_11x13_2floors",
    "valid_ratio": 0.875,
    "distinct_layouts": 32,
    "distinct_valid": 28,
    "top_area_accuracy": 0.8635,
    "top_hard_violations": 0,
    "notes": "StairCore 1.8x4.2 + diversity 0.85",
}

"""Phase 6.3 — Validation + Repair。"""

from __future__ import annotations

import pytest

from packages.llm import (
    LLMIngestError,
    LLMRepairExhaustedError,
    MockLLMProvider,
    StructuredRequirementParser,
    ingest_llm_requirement,
    parse_requirement_text_with_repair,
)
from packages.llm.repair import build_repair_prompt


def _ok_draft():
    return {
        "known": {
            "floor_count": 2,
            "household": {"bedrooms": 3},
            "spaces": [
                {
                    "id": "living",
                    "name": "客厅",
                    "category": "public",
                    "floor_preference": ["F1"],
                }
            ],
        },
        "assumptions": [],
        "unknowns": [{"key": "site.width", "description": "未给"}],
    }


def test_ingest_geometry_becomes_llm_ingest_error():
    with pytest.raises(LLMIngestError) as ei:
        ingest_llm_requirement(
            {
                "known": {"spaces": [{"name": "客厅", "x": 1.0, "y": 2.0}]},
                "assumptions": [],
                "unknowns": [],
            }
        )
    assert any(i.code == "req.geometry_forbidden" for i in ei.value.issues)


def test_repair_prompt_includes_errors_and_previous():
    prompt = build_repair_prompt(
        "两层三卧",
        errors=["含几何字段 $.known.spaces[0].x"],
        previous={"known": {"spaces": [{"name": "客厅", "x": 1}]}},
    )
    assert "几何" in prompt or "x" in prompt
    assert "两层三卧" in prompt
    assert '"x"' in prompt or "x" in prompt


def test_repair_succeeds_on_second_attempt():
    bad = {
        "known": {
            "floor_count": 1,
            "spaces": [{"name": "书房", "floor_preference": ["F2"]}],
        },
        "assumptions": [],
        "unknowns": [],
    }
    good = {
        "known": {
            "floor_count": 1,
            "spaces": [{"name": "书房", "floor_preference": ["F1"]}],
        },
        "assumptions": [],
        "unknowns": [],
    }
    provider = MockLLMProvider([bad, good])
    result = parse_requirement_text_with_repair(
        "一层带书房",
        provider=provider,
        max_repairs=2,
    )
    assert result.repaired
    assert result.attempts == 2
    assert len(result.repair_notes) == 1
    assert result.spec.spaces[0].floor_preference == ["F1"]


def test_repair_geometry_then_ok():
    bad = {
        "known": {"spaces": [{"name": "客厅", "x": 0, "y": 0}]},
        "assumptions": [],
        "unknowns": [],
    }
    provider = MockLLMProvider([bad, _ok_draft()])
    result = StructuredRequirementParser(provider).parse_with_repair("两层三卧")
    assert result.spec.floor_count == 2
    assert result.attempts == 2


def test_repair_exhausted():
    bad = {
        "known": {
            "floor_count": 1,
            "spaces": [{"name": "书房", "floor_preference": ["F3"]}],
        },
        "assumptions": [],
        "unknowns": [],
    }
    provider = MockLLMProvider([bad, bad, bad])
    with pytest.raises(LLMRepairExhaustedError) as ei:
        parse_requirement_text_with_repair(
            "坏输出",
            provider=provider,
            max_repairs=2,
        )
    assert ei.value.attempts == 3
    assert len(ei.value.errors) == 3


def test_max_repairs_zero_is_single_shot_fail():
    bad = {
        "known": {
            "floor_count": 1,
            "spaces": [{"name": "书房", "floor_preference": ["F2"]}],
        },
        "assumptions": [],
        "unknowns": [],
    }
    provider = MockLLMProvider([bad])
    with pytest.raises(LLMRepairExhaustedError) as ei:
        parse_requirement_text_with_repair(
            "x",
            provider=provider,
            max_repairs=0,
        )
    assert ei.value.attempts == 1

"""Phase 6.0 — LLM 边界与 ingest gate。"""

from __future__ import annotations

import pytest
from solver.program.requirements_normalize import normalize_requirements_to_program

from packages.llm import (
    SYSTEM_PROMPT_SKELETON,
    GeometryForbiddenError,
    MockLLMProvider,
    assert_no_geometry_payload,
    ingest_llm_requirement,
)
from packages.llm.gate import LLMIngestError
from packages.schema.llm_contract import LLMRequirementDraft


def test_reject_geometry_keys():
    with pytest.raises(GeometryForbiddenError) as ei:
        assert_no_geometry_payload(
            {
                "known": {
                    "spaces": [
                        {"name": "客厅", "x": 1.0, "y": 2.0, "width": 3, "depth": 4}
                    ]
                }
            }
        )
    assert any("x" in k for k in ei.value.keys)


def test_allow_site_size_and_target_area():
    assert_no_geometry_payload(
        {
            "known": {
                "floor_count": 2,
                "site": {"width": 11, "depth": 13},
                "spaces": [{"name": "客厅", "target_area": 24, "min_width": 3.0}],
            },
            "assumptions": [],
            "unknowns": [],
        }
    )


def test_ingest_happy_path_to_requirement_spec():
    raw = {
        "raw_text": "两层三卧，客厅朝南",
        "known": {
            "floor_count": 2,
            "household": {"bedrooms": 3},
            "preferences": {"prefer_south_facing_living": True},
            "spaces": [
                {
                    "id": "living",
                    "name": "客厅",
                    "category": "public",
                    "floor_preference": ["F1"],
                }
            ],
            "relation_intents": [
                {
                    "a": "厨房",
                    "b": "餐厅",
                    "kind": "adjacency",
                    "strength": "preferred",
                }
            ],
        },
        "assumptions": [
            {
                "key": "bathrooms",
                "value": 2,
                "reason": "用户未指定，住宅默认",
            }
        ],
        "unknowns": [
            {"key": "site.entrance_edge", "description": "未说明入口方向"}
        ],
    }
    result = ingest_llm_requirement(raw)
    assert result.spec.floor_count == 2
    assert result.spec.household.bedrooms == 3
    assert result.spec.raw_text == "两层三卧，客厅朝南"
    assert len(result.spec.assumptions) == 1
    assert len(result.spec.unknowns) == 1
    assert len(result.spec.relation_intents) == 1
    assert result.semantic.ok


def test_ingest_rejects_bad_floor_preference():
    raw = {
        "known": {
            "floor_count": 2,
            "spaces": [
                {"name": "书房", "floor_preference": ["F3"]},
            ],
        }
    }
    with pytest.raises(LLMIngestError) as ei:
        ingest_llm_requirement(raw)
    assert any(i.code == "req.floor_preference_range" for i in ei.value.issues)


def test_ingest_rejects_illegal_floor_id():
    raw = {
        "known": {
            "floor_count": 2,
            "spaces": [{"name": "书房", "floor_preference": ["F7"]}],
        }
    }
    with pytest.raises(LLMIngestError) as ei:
        ingest_llm_requirement(raw)
    assert any(i.code == "req.floor_preference" for i in ei.value.issues)


def test_mock_provider_and_system_prompt():
    provider = MockLLMProvider(
        [
            {
                "known": {"floor_count": 1, "household": {"bedrooms": 2}},
                "assumptions": [],
                "unknowns": [{"key": "site.width", "description": "未给场地"}],
            }
        ]
    )
    assert "禁止" in SYSTEM_PROMPT_SKELETON or "几何" in SYSTEM_PROMPT_SKELETON
    data = provider.complete_json(system=SYSTEM_PROMPT_SKELETON, user="小两居")
    result = ingest_llm_requirement(data, raw_text="小两居")
    assert result.spec.floor_count == 1
    assert result.spec.raw_text == "小两居"


def test_draft_to_spec_normalizes():
    """边界产物可进入现有 Normalizer（不要求可解完备）。"""
    draft = LLMRequirementDraft.model_validate(
        {
            "known": {
                "floor_count": 2,
                "site": {"width": 11, "depth": 13},
                "household": {
                    "bedrooms": 3,
                    "bathrooms": 2,
                    "has_garage": True,
                },
                "spaces": [
                    {
                        "id": "living",
                        "name": "客厅",
                        "category": "public",
                        "target_area": 24,
                        "floor_preference": ["F1"],
                    },
                    {
                        "id": "bed1",
                        "name": "主卧",
                        "category": "private",
                        "target_area": 16,
                        "floor_preference": ["F2"],
                    },
                ],
            },
            "assumptions": [],
            "unknowns": [],
        }
    )
    spec = draft.to_requirement_spec()
    program = normalize_requirements_to_program(spec)
    assert program.site.width == 11
    assert len(program.floors) == 2
    assert len(program.rooms) >= 2

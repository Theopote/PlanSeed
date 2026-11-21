"""Intent LLM 草稿 Gate 与 Hybrid 合并。"""

from __future__ import annotations

import pytest

from packages.llm.boundary import GeometryForbiddenError
from packages.llm.intent_draft import gate_intent_draft
from packages.llm.intent_parser import parse_intent_patch
from packages.llm.mock import MockLLMProvider
from packages.schema.intent_patch import IntentChangeAction


def test_gate_rejects_geometry():
    with pytest.raises(GeometryForbiddenError):
        gate_intent_draft(
            {
                "preserve": ["living"],
                "changes": [{"action": "increase_target_area", "target": "master_bedroom", "x": 1}],
            }
        )


def test_gate_filters_unknown_actions():
    out = gate_intent_draft(
        {
            "preserve": ["客厅"],
            "changes": [
                {"action": "teleport_room", "target": "living"},
                {
                    "action": "require_adjacency",
                    "target": "kitchen",
                    "partner": "dining",
                    "priority": "required",
                },
            ],
            "regeneration": "partial",
        }
    )
    assert len(out["changes"]) == 1
    assert out["changes"][0]["action"] == "require_adjacency"


def test_hybrid_merges_llm_draft_without_duplicating_deterministic():
    draft = {
        "preserve": ["kitchen"],
        "changes": [
            {
                "action": "increase_target_area",
                "target": "master_bedroom",
                "value": 0.2,
            },
            {
                "action": "require_adjacency",
                "target": "kitchen",
                "partner": "dining",
            },
        ],
        "regeneration": "partial",
    }
    patch = parse_intent_patch(
        "保持客厅不变，主卧大一点",
        llm_draft=draft,
    )
    assert "living" in patch.preserve or "kitchen" in patch.preserve
    assert "kitchen" in patch.preserve
    actions = [c.action for c in patch.changes]
    assert IntentChangeAction.INCREASE_TARGET_AREA in actions
    assert IntentChangeAction.REQUIRE_ADJACENCY in actions
    # 主卧增大不因 draft 再复制一条
    master_incs = [
        c
        for c in patch.changes
        if c.action == IntentChangeAction.INCREASE_TARGET_AREA
        and c.target == "master_bedroom"
    ]
    assert len(master_incs) == 1
    assert patch.source == "hybrid"


def test_provider_failure_falls_back_deterministic():
    class Boom:
        def complete_json(self, *, system: str, user: str):
            raise RuntimeError("ollama down")

    patch = parse_intent_patch("主卧大一点", provider=Boom())
    assert any(
        c.action == IntentChangeAction.INCREASE_TARGET_AREA for c in patch.changes
    )
    assert patch.source == "user"


def test_mock_provider_draft_is_gated_and_merged():
    mock = MockLLMProvider(
        responses=[
            {
                "preserve": ["living"],
                "changes": [
                    {
                        "action": "avoid_adjacency",
                        "target": "kitchen",
                        "partner": "bedroom",
                    }
                ],
                "regeneration": "partial",
            }
        ]
    )
    patch = parse_intent_patch("厨房远离卧室", provider=mock)
    assert any(c.action == IntentChangeAction.AVOID_ADJACENCY for c in patch.changes)

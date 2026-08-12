"""Draft coerce — schema 缓冲层单测。"""

from __future__ import annotations

from packages.llm.coerce import coerce_llm_draft_payload
from packages.llm.gate import ingest_llm_requirement


def test_coerce_string_scalars_and_bool():
    payload = coerce_llm_draft_payload(
        {
            "known": {
                "floor_count": "2",
                "household": {
                    "bedrooms": "3",
                    "bathrooms": "2",
                    "has_garage": "true",
                },
                "site": {"width": "12", "depth": "14米"},
                "preferences": {"prefer_south_facing_living": "是"},
            },
            "assumptions": [],
            "unknowns": ["site.entrance_edge"],
        }
    )
    k = payload["known"]
    assert k["floor_count"] == 2
    assert k["household"]["bedrooms"] == 3
    assert k["household"]["has_garage"] is True
    assert k["site"]["width"] == 12.0
    assert k["site"]["depth"] == 14.0
    assert k["preferences"]["prefer_south_facing_living"] is True
    assert payload["unknowns"][0]["key"] == "site.entrance_edge"


def test_coerce_relation_kind_aliases_and_drop_unknown():
    payload = coerce_llm_draft_payload(
        {
            "known": {
                "relation_intents": [
                    {"a": "厨房", "b": "餐厅", "kind": "nearby"},
                    {"a": "客厅", "b": "餐厅", "kind": "连通"},
                    {"a": "主卧", "b": "客厅", "kind": "totally_made_up"},
                    {"a": "", "b": "客厅", "kind": "near"},
                ]
            }
        }
    )
    rels = payload["known"]["relation_intents"]
    assert len(rels) == 2
    kinds = {(r["a"], r["kind"], r["b"]) for r in rels}
    assert ("厨房", "near", "餐厅") in kinds
    assert ("客厅", "open_connection", "餐厅") in kinds


def test_coerce_space_string_and_floor_orientation():
    payload = coerce_llm_draft_payload(
        {
            "known": {
                "spaces": [
                    "客厅",
                    {
                        "name": "书房",
                        "floor_preference": ["一层", "2"],
                        "preferred_orientation": "朝北",
                    },
                ]
            }
        }
    )
    spaces = payload["known"]["spaces"]
    assert spaces[0] == {"name": "客厅"}
    assert spaces[1]["floor_preference"] == ["F1", "F2"]
    assert spaces[1]["preferred_orientation"] == "north"


def test_ingest_accepts_coerced_messy_draft():
    result = ingest_llm_requirement(
        {
            "raw_text": "两层三卧两卫，厨房靠近餐厅",
            "known": {
                "floor_count": "2",
                "household": {"bedrooms": "3", "bathrooms": 2},
                "spaces": [{"name": "厨房"}, {"name": "餐厅"}],
                "relation_intents": [
                    {"a": "厨房", "b": "餐厅", "kind": "nearby"},
                ],
            },
            "assumptions": [
                {
                    "key": "household.has_garage",
                    "value": False,
                    "source": "llm_inference",
                }
            ],
            "unknowns": [],
        },
        raw_text="两层三卧两卫，厨房靠近餐厅",
    )
    assert result.spec.floor_count == 2
    assert result.draft.known.household.bedrooms == 3
    # ADR-003：llm_inference 转 unknown（spec 层可见）
    assert "household.has_garage" in {u.key for u in result.spec.unknowns}
    assert any(
        {r.a, r.b} == {"厨房", "餐厅"} and r.kind == "near"
        for r in result.draft.known.relation_intents
    )

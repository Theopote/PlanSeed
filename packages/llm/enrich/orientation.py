"""Orientation stage — preferred_orientation + prefer_south_facing_living."""

from __future__ import annotations

from packages.llm.enrich._text import living_prefers_south, surface_forms_for_space
from packages.llm.enrich.context import EnrichmentContext
from packages.llm.vocabulary import canonical_zh_for_alias
from packages.schema.site import CardinalOrientation

_ORIENT_PHRASES: tuple[tuple[str, CardinalOrientation], ...] = (
    ("朝南", CardinalOrientation.SOUTH),
    ("朝北", CardinalOrientation.NORTH),
    ("朝东", CardinalOrientation.EAST),
    ("朝西", CardinalOrientation.WEST),
    ("要南向", CardinalOrientation.SOUTH),
    ("要北向", CardinalOrientation.NORTH),
    ("南向", CardinalOrientation.SOUTH),
    ("北向", CardinalOrientation.NORTH),
    ("东向", CardinalOrientation.EAST),
    ("西向", CardinalOrientation.WEST),
    ("偏南", CardinalOrientation.SOUTH),
    ("偏北", CardinalOrientation.NORTH),
    ("偏东", CardinalOrientation.EAST),
    ("偏西", CardinalOrientation.WEST),
)


def orientation_for_space(name: str, text: str) -> CardinalOrientation | None:
    for surf in surface_forms_for_space(name):
        for phrase, ori in _ORIENT_PHRASES:
            if f"{surf}{phrase}" in text or f"{phrase}{surf}" in text:
                return ori
    return None


class OrientationStage:
    def apply(self, context: EnrichmentContext) -> EnrichmentContext:
        known = context.known
        text = context.text
        notes = context.notes

        space_names = {
            canonical_zh_for_alias(s.name.strip())
            for s in known.spaces
            if s.name
        }
        space_by_name = {
            canonical_zh_for_alias(s.name): i for i, s in enumerate(known.spaces)
        }
        for name in list(space_names):
            i = space_by_name.get(name)
            if i is None:
                continue
            sp = known.spaces[i]
            if sp.preferred_orientation is None:
                ori = orientation_for_space(name, text)
                if ori is not None:
                    known.spaces[i] = sp.model_copy(
                        update={"preferred_orientation": ori}
                    )
                    notes.append(f"朝向:{name}={ori}")
                    context.record("orientation", str(ori), name)
                    if name == "客厅" and ori == CardinalOrientation.SOUTH:
                        if known.preferences.prefer_south_facing_living is None:
                            known.preferences.prefer_south_facing_living = True

        if known.preferences.prefer_south_facing_living is None and living_prefers_south(
            text
        ):
            known.preferences.prefer_south_facing_living = True
            notes.append("prefer_south_facing_living")
            context.record("orientation", "prefer_south_facing_living")
        return context

"""Candidate 序列化含 per-floor SVG。"""

from backend.services.serialization import serialize_candidate
from solver.generators.guillotine import GuillotineGenerator
from solver.tests.test_guillotine import benchmark_program


def test_serialize_candidate_includes_floor_svgs():
    program = benchmark_program()
    cand = GuillotineGenerator().generate(program, seed=0)
    payload = serialize_candidate(program, cand, 0)
    assert payload.svg
    assert set(payload.floor_svgs) == {f.floor_id for f in cand.floors}
    for fid, svg in payload.floor_svgs.items():
        assert f'data-floor-id="{fid}"' in svg

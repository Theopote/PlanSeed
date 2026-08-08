"""SVG debug 渲染测试。"""

from __future__ import annotations

from pathlib import Path

from solver.generators.guillotine import GuillotineGenerator
from solver.tests.test_guillotine import benchmark_program
from solver.visualize.svg import render_candidate_svg, write_candidate_svg


def test_render_candidate_svg_contains_rooms_and_meta(tmp_path: Path):
    program = benchmark_program()
    candidate = GuillotineGenerator().generate(program, seed=0)
    svg = render_candidate_svg(
        candidate,
        floor_width=program.buildable.width,
        floor_depth=program.buildable.depth,
        floor_labels={fl.id: fl.label or fl.id for fl in program.floors},
    )
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert "seed=0" in svg
    assert 'class="room-shape"' in svg
    assert "data-room-id=" in svg
    assert "客厅" in svg or "主卧" in svg
    assert "wet" in svg.lower() or "湿" in svg or "stroke-dasharray" in svg

    out = write_candidate_svg(
        candidate,
        tmp_path / "c.svg",
        floor_width=program.buildable.width,
        floor_depth=program.buildable.depth,
    )
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("<svg")

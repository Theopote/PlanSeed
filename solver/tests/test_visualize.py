"""SVG 渲染测试 — customer（默认）与 debug 双模式。"""

from __future__ import annotations

import re
from pathlib import Path

from pytest import raises
from solver.generators.guillotine import GuillotineGenerator
from solver.tests.test_guillotine import benchmark_program
from solver.tests.test_vertical_void_prededuction import _program_with_atrium
from solver.visualize.svg import (
    render_candidate_svg,
    render_floor_svg,
    write_candidate_svg,
)


def _room_id_texts(svg: str) -> set[str]:
    """提取作为可见文字渲染的 room_id（Consolas 调试行）。"""
    return set(re.findall(r'font-family="Consolas, monospace">([^<]+)</text>', svg))


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
    assert 'class="room-node"' in svg
    assert "data-room-id=" in svg
    assert "客厅" in svg or "主卧" in svg

    out = write_candidate_svg(
        candidate,
        tmp_path / "c.svg",
        floor_width=program.buildable.width,
        floor_depth=program.buildable.depth,
    )
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("<svg")


def test_render_floor_svg_is_single_floor():
    program = benchmark_program()
    candidate = GuillotineGenerator().generate(program, seed=0)
    assert len(candidate.floors) >= 1
    fid = candidate.floors[0].floor_id
    svg = render_floor_svg(
        candidate,
        fid,
        floor_width=program.buildable.width,
        floor_depth=program.buildable.depth,
        floor_labels={fl.id: fl.label or fl.id for fl in program.floors},
    )
    assert f'data-floor-id="{fid}"' in svg
    assert 'class="room-shape"' in svg
    with raises(ValueError, match="floor_id 不存在"):
        render_floor_svg(
            candidate,
            "no-such-floor",
            floor_width=program.buildable.width,
            floor_depth=program.buildable.depth,
        )


def test_customer_mode_hides_debug_labels() -> None:
    program = _program_with_atrium()
    candidate = GuillotineGenerator().generate(program, seed=0)
    room_ids = {r.id for r in program.rooms}
    svg = render_candidate_svg(
        candidate,
        floor_width=program.buildable.width,
        floor_depth=program.buildable.depth,
        floor_labels={fl.id: fl.label or fl.id for fl in program.floors},
        site=program.site,
    )
    visible_ids = _room_id_texts(svg)
    assert not (room_ids & visible_ids), f"customer 模式不应显示 room_id 文字：{visible_ids}"
    assert ">WS</text>" not in svg
    assert ">ENTRY</text>" not in svg
    assert ">ATRIUM</text>" not in svg
    assert "入口" in svg
    assert "天窗" in svg
    assert 'class="skylight-marker"' in svg
    assert "天井" in svg


def test_debug_mode_keeps_debug_labels() -> None:
    program = _program_with_atrium()
    candidate = GuillotineGenerator().generate(program, seed=0)
    room_ids = {r.id for r in program.rooms}
    svg = render_candidate_svg(
        candidate,
        floor_width=program.buildable.width,
        floor_depth=program.buildable.depth,
        floor_labels={fl.id: fl.label or fl.id for fl in program.floors},
        site=program.site,
        render_mode="debug",
    )
    visible_ids = _room_id_texts(svg)
    assert room_ids & visible_ids, "debug 模式应显示至少一个 room_id 文字"
    assert ">WS</text>" in svg or "WS</text>" in svg
    assert ">ENTRY</text>" in svg
    assert ">ATRIUM</text>" in svg
    assert "atrium_voids=" in svg
    assert "skylight=True" in svg
    assert 'data-kind="atrium"' in svg
    assert 'data-void-id="atrium-1"' in svg


def test_render_atrium_skylight_overlay_customer() -> None:
    program = _program_with_atrium()
    candidate = GuillotineGenerator().generate(program, seed=0)
    svg = render_candidate_svg(
        candidate,
        floor_width=program.buildable.width,
        floor_depth=program.buildable.depth,
        floor_labels={fl.id: fl.label or fl.id for fl in program.floors},
    )
    assert "atrium_voids=" in svg
    assert "skylight=True" in svg
    assert 'data-kind="atrium"' in svg
    assert "ATRIUM" not in svg
    assert "天窗" in svg
    assert 'class="skylight-marker"' in svg

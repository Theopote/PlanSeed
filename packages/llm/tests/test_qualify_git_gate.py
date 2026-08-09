"""严格资格认证：--gate 要求干净 git 工作区。"""

from __future__ import annotations

import pytest

from packages.llm.benchmark.qualify import (
    QualificationError,
    git_is_dirty,
    main,
    require_clean_worktree_for_gate,
)


def test_require_clean_worktree_raises_when_dirty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "packages.llm.benchmark.qualify.git_is_dirty",
        lambda: True,
    )
    monkeypatch.setattr(
        "packages.llm.benchmark.qualify._git_dirty_paths",
        lambda limit=40: ["packages/llm/benchmark/blind_cases_v4.py"],
    )
    with pytest.raises(QualificationError) as ei:
        require_clean_worktree_for_gate()
    assert "clean git worktree" in str(ei.value)
    assert "git_dirty=true" in str(ei.value)


def test_require_clean_worktree_ok_when_clean(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "packages.llm.benchmark.qualify.git_is_dirty",
        lambda: False,
    )
    require_clean_worktree_for_gate()  # 不抛


def test_gate_main_refuses_dirty_before_run(monkeypatch: pytest.MonkeyPatch):
    """--gate + dirty → exit 2，且不调用 run_qualification。"""
    monkeypatch.setattr(
        "packages.llm.benchmark.qualify.git_is_dirty",
        lambda: True,
    )
    monkeypatch.setattr(
        "packages.llm.benchmark.qualify._git_dirty_paths",
        lambda limit=40: ["dirty.py"],
    )

    called = {"run": False}

    def _boom(**_kwargs):
        called["run"] = True
        raise AssertionError("should not run qualification on dirty --gate")

    monkeypatch.setattr(
        "packages.llm.benchmark.qualify.run_qualification",
        _boom,
    )
    code = main(["--gate", "--limit", "1"])
    assert code == 2
    assert called["run"] is False


def test_without_gate_dirty_still_allows_entry(monkeypatch: pytest.MonkeyPatch):
    """无 --gate 时脏工作区不挡入口（工程跑分仍可记 git_dirty）。"""
    monkeypatch.setattr(
        "packages.llm.benchmark.qualify.git_is_dirty",
        lambda: True,
    )
    # 在解析后、连 Ollama 前就因缺模型/mock 可能失败；只断言硬门未拦
    # 用提前抛错的 stub，确认已越过 dirty gate
    entered = {"ok": False}

    def _stub(**_kwargs):
        entered["ok"] = True
        raise RuntimeError("stop-after-gate-check")

    monkeypatch.setattr(
        "packages.llm.benchmark.qualify.run_qualification",
        _stub,
    )
    monkeypatch.setattr(
        "packages.llm.benchmark.qualify.load_ollama_config",
        lambda: type(
            "Cfg",
            (),
            {"base_url": "http://127.0.0.1:11434", "model": "mock"},
        )(),
    )
    with pytest.raises(RuntimeError, match="stop-after-gate-check"):
        main(["--limit", "1", "--set", "development"])
    assert entered["ok"] is True


def test_git_is_dirty_reads_porcelain(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "packages.llm.benchmark.qualify.subprocess.check_output",
        lambda *a, **k: " M packages/llm/benchmark/qualify.py\n",
    )
    assert git_is_dirty() is True
    monkeypatch.setattr(
        "packages.llm.benchmark.qualify.subprocess.check_output",
        lambda *a, **k: "",
    )
    assert git_is_dirty() is False

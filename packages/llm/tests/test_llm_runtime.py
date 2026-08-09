"""Application LLM Runtime — 共享 Provider / 连接池。"""

from __future__ import annotations

from packages.llm.mock import MockLLMProvider
from packages.llm.runtime import (
    get_shared_requirement_provider,
    reset_shared_requirement_provider,
    set_shared_requirement_provider,
)


class _CloseProbe(MockLLMProvider):
    def __init__(self) -> None:
        super().__init__([{"known": {}, "assumptions": [], "unknowns": []}])
        self.closed = False

    def close(self) -> None:
        self.closed = True


def setup_function() -> None:
    reset_shared_requirement_provider()


def teardown_function() -> None:
    reset_shared_requirement_provider()


def test_shared_provider_reused():
    a = MockLLMProvider([{"known": {}, "assumptions": [], "unknowns": []}])
    set_shared_requirement_provider(a)
    assert get_shared_requirement_provider() is a
    assert get_shared_requirement_provider() is a


def test_reset_closes_runtime_owned_provider(monkeypatch):
    probe = _CloseProbe()

    def _fake_create(**kwargs):
        return probe

    monkeypatch.setattr(
        "packages.llm.runtime.create_requirement_llm_provider",
        _fake_create,
    )
    reset_shared_requirement_provider()
    got = get_shared_requirement_provider()
    assert got is probe
    assert probe.closed is False
    reset_shared_requirement_provider()
    assert probe.closed is True
    # 再次 get 会新建
    probe2 = _CloseProbe()

    def _fake_create2(**kwargs):
        return probe2

    monkeypatch.setattr(
        "packages.llm.runtime.create_requirement_llm_provider",
        _fake_create2,
    )
    assert get_shared_requirement_provider() is probe2


def test_get_nl_provider_uses_shared_runtime():
    from backend.services.nl_parse import get_nl_provider, set_nl_provider_factory

    set_nl_provider_factory(None)
    reset_shared_requirement_provider()
    fake = MockLLMProvider([{"known": {}, "assumptions": [], "unknowns": []}])
    set_shared_requirement_provider(fake)
    try:
        assert get_nl_provider() is fake
        assert get_nl_provider() is fake
    finally:
        set_shared_requirement_provider(None)
        reset_shared_requirement_provider()


def test_injected_provider_not_closed_on_replace():
    first = _CloseProbe()
    second = _CloseProbe()
    set_shared_requirement_provider(first)
    set_shared_requirement_provider(second)
    assert first.closed is False  # 注入实例由调用方负责
    assert get_shared_requirement_provider() is second

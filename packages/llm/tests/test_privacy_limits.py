"""Phase 7.5-I — Ollama privacy + RuntimeLimits。"""

from __future__ import annotations

import pytest

from packages.llm.health import LlmHealthState, probe_llm_health
from packages.llm.ollama import OllamaConfig, OllamaProvider
from packages.llm.privacy import (
    OllamaRemoteBlockedError,
    enforce_ollama_endpoint_policy,
    ollama_endpoint_is_loopback,
    remote_model_warning,
)
from packages.schema.limits import API_LIMITS, RUNTIME_LIMITS, SOLVER_LIMITS


def test_loopback_hosts_allowed():
    assert ollama_endpoint_is_loopback("http://127.0.0.1:11434")
    assert ollama_endpoint_is_loopback("http://localhost:11434")
    assert ollama_endpoint_is_loopback("http://[::1]:11434")
    enforce_ollama_endpoint_policy("http://127.0.0.1:11434")


def test_remote_blocked_by_default():
    with pytest.raises(OllamaRemoteBlockedError) as ei:
        enforce_ollama_endpoint_policy("http://8.8.8.8:11434")
    assert "REMOTE MODEL WARNING" in str(ei.value)


def test_remote_allowed_with_env():
    enforce_ollama_endpoint_policy(
        "https://ollama.example.com",
        environ={"PLANSEED_OLLAMA_ALLOW_REMOTE": "1"},
    )


def test_provider_init_blocks_remote():
    with pytest.raises(OllamaRemoteBlockedError):
        OllamaProvider(OllamaConfig(base_url="http://10.0.0.2:11434"))


def test_provider_skip_policy_for_injected_client():
    # skip_endpoint_policy：测试注入路径
    p = OllamaProvider(
        OllamaConfig(base_url="http://10.0.0.2:11434"),
        skip_endpoint_policy=True,
    )
    p.close()


def test_probe_health_blocks_remote():
    status = probe_llm_health(
        environ={
            "PLANSEED_LLM_PROVIDER": "ollama",
            "PLANSEED_OLLAMA_BASE_URL": "http://203.0.113.1:11434",
            "PLANSEED_OLLAMA_ALLOW_REMOTE": "0",
        }
    )
    assert status.state == LlmHealthState.LLM_UNAVAILABLE
    assert status.endpoint_remote is True
    assert status.remote_blocked is True
    assert status.detail and "REMOTE MODEL WARNING" in status.detail


def test_remote_warning_text():
    msg = remote_model_warning("http://example.com:11434")
    assert msg.startswith("REMOTE MODEL WARNING")


def test_runtime_limits_constants():
    assert RUNTIME_LIMITS.solver is SOLVER_LIMITS
    assert RUNTIME_LIMITS.api is API_LIMITS
    assert SOLVER_LIMITS.max_floors == 3
    assert API_LIMITS.max_nl_text_chars == 8000
    assert API_LIMITS.max_generate_candidates == 64

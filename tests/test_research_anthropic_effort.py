"""Offline fake-SDK checks for explicit Anthropic effort; no credential/network use."""

import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest

from src.providers.anthropic_adapter import AnthropicAdapter
from src.providers.base import ProviderError


@pytest.fixture
def sdk(monkeypatch):
    """Purpose: capture SDK construction and dispatch. Parameters: monkeypatch.
    Returns: mutable call log/error control. Failures: explicit fake provider errors
    propagate; any attempt to read real credential files fails the test.
    """
    observed = {"clients": [], "requests": [], "error": None, "stop_reason": "end_turn"}

    def no_credentials():
        """Purpose: prevent real credential reads. Parameters: none. Returns: never.
        Failures: AssertionError if a test accidentally reaches credential lookup.
        """
        raise AssertionError("Tests must not read real credentials")

    def create(**kwargs):
        """Purpose: mimic one SDK request. Parameters: request kwargs.
        Returns: synthetic message. Failures: configured fake provider exception.
        """
        observed["requests"].append(deepcopy(kwargs))
        if observed["error"] is not None:
            raise observed["error"]
        return SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking="Not response text"),
                     SimpleNamespace(type="text", text='{"ok":true}')],
            usage=SimpleNamespace(input_tokens=12, output_tokens=34,
                                  cache_read_input_tokens=5, cache_creation_input_tokens=7),
            stop_reason=observed["stop_reason"],
        )

    def client(**kwargs):
        """Purpose: capture SDK initialization. Parameters: client kwargs.
        Returns: fake messages endpoint. Failures: none; no SDK/network is loaded.
        """
        observed["clients"].append(deepcopy(kwargs))
        return SimpleNamespace(messages=SimpleNamespace(create=create))

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=client))
    monkeypatch.setattr("src.providers.anthropic_adapter.get_claude_key", no_credentials)
    monkeypatch.setattr("src.providers.anthropic_adapter.get_claude_workspace_id", no_credentials)
    return observed


def adapter(**overrides):
    """Purpose: construct a credential-free fixture. Parameters: option overrides.
    Returns: configured adapter. Failures: normal adapter validation errors.
    """
    options = {"model_id": "claude-sonnet-5-5", "api_key": "synthetic-test-key",
               "workspace_id": "synthetic-workspace", "max_tokens": 8000,
               "timeout_seconds": 240.0, "offline_mode": False}
    options.update(overrides)
    return AnthropicAdapter(**options)


@pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh", "max"])
def test_effort_preserves_model_workspace_token_ceiling_and_usage(sdk, effort):
    """Purpose: verify explicit effort forwarding. Parameters: sdk, effort.
    Returns: None. Failures: assertions for lost bindings, fallback, or token edits.
    """
    model = adapter(effort=effort)
    result = model.generate("Proposal request", system_prompt="System", cached_context="Evidence")
    assert sdk["clients"] == [{"api_key": "synthetic-test-key", "timeout": 240.0,
                                "max_retries": 0,
                                "default_headers": {"anthropic-workspace-id": "synthetic-workspace"}}]
    assert sdk["requests"] == [{"model": "claude-sonnet-5-5", "max_tokens": 8000,
                                 "messages": [{"role": "user", "content": "Proposal request"}],
                                 "workspace_id": "synthetic-workspace",
                                 "output_config": {"effort": effort},
                                 "system": [{"type": "text", "text": "System"},
                                            {"type": "text", "text": "Evidence",
                                             "cache_control": {"type": "ephemeral"}}]}]
    assert result.model_id == model.model_id == "claude-sonnet-5-5"
    assert model.max_tokens == 8000 and model.effort == effort
    assert result.provider == "anthropic" and result.content == '{"ok":true}'
    assert result.usage.input_tokens == 12 and result.usage.output_tokens == 34
    assert result.usage.cached_input_tokens == 5 and result.usage.cache_write_tokens == 7


@pytest.mark.parametrize("missing_attribute", [False, True])
def test_default_or_missing_effort_preserves_exact_legacy_request(sdk, missing_attribute):
    """Purpose: retain existing behavior. Parameters: sdk, missing_attribute flag.
    Returns: None. Failures: assertions if output_config/thinking parameters appear.
    """
    model = adapter(workspace_id="")
    assert model.effort is None
    if missing_attribute:
        del model.effort
    model.generate("Legacy request")
    assert sdk["requests"] == [{"model": "claude-sonnet-5-5", "max_tokens": 8000,
                                 "messages": [{"role": "user", "content": "Legacy request"}]}]
    assert sdk["clients"][0]["default_headers"] is None


def test_runner_can_switch_effort_without_stale_settings_or_model_change(sdk):
    """Purpose: support per-stage runner settings. Parameters: sdk. Returns: None.
    Failures: assertions if effort sticks across calls or changes another option.
    """
    model = adapter()
    for value in ("medium", "high", None):
        model.effort = value
        model.generate("Current stage")
    assert [request.get("output_config") for request in sdk["requests"]] == [
        {"effort": "medium"}, {"effort": "high"}, None]
    assert all(r["model"] == "claude-sonnet-5-5" and r["max_tokens"] == 8000
               for r in sdk["requests"])


@pytest.mark.parametrize("effort", ["", "HIGH", " medium ", "invalid", 1, True, [], {}])
def test_invalid_effort_rejected_before_sdk_construction(sdk, effort):
    """Purpose: fail invalid runner configuration before dispatch. Parameters: sdk, effort.
    Returns: None. Failures: assertions if malformed values reach the SDK.
    """
    model = adapter()
    model.effort = effort
    with pytest.raises(ValueError, match="Anthropic effort"):
        model.generate("Never dispatched")
    assert sdk["clients"] == [] and sdk["requests"] == []


def test_provider_rejection_does_not_retry_or_fall_back(sdk):
    """Purpose: preserve fail-closed provider errors. Parameters: sdk. Returns: None.
    Failures: assertions for silent fallback, retry, or discarded exception details.
    """
    failure = RuntimeError("Synthetic provider rejection")
    sdk["error"] = failure
    with pytest.raises(ProviderError) as caught:
        adapter(effort="high").generate("One attempt")
    assert caught.value.raw_error is failure
    assert len(sdk["clients"]) == len(sdk["requests"]) == 1
    assert sdk["requests"][0]["model"] == "claude-sonnet-5-5"
    assert sdk["requests"][0]["output_config"] == {"effort": "high"}


def test_effort_does_not_hide_truncation_or_make_continuation_calls(sdk):
    """Purpose: retain observed truncation for parent's stop guard. Parameters: sdk.
    Returns: None. Failures: assertions for auto-retry, altered ceiling or hidden stop.
    """
    sdk["stop_reason"] = "max_tokens"
    result = adapter(effort="high").generate("Proposal")
    assert result.was_truncated and result.finish_reason == "max_tokens"
    assert len(sdk["requests"]) == 1 and sdk["requests"][0]["max_tokens"] == 8000


def test_offline_mode_with_effort_never_constructs_sdk(sdk):
    """Purpose: preserve offline execution. Parameters: sdk. Returns: None.
    Failures: assertions if configuring effort causes a paid/offline SDK call.
    """
    result = adapter(effort="medium", offline_mode=True).generate("Offline fixture")
    assert result.model_id == "claude-sonnet-5-5"
    assert sdk["clients"] == [] and sdk["requests"] == []

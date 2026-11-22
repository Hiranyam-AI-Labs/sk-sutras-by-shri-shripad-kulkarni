"""
================================================================================
Test Module: tests.test_providers
Author: Hiranyam AI Labs (https://hiranyamai.com/)
Project: SK Sutras - by Shri Shripad Kulkarni
Description: QA unit tests verifying the unified provider adapter framework,
             offline execution safety, token estimation, and dynamic model switching.
================================================================================
"""

import pytest
import socket
from types import SimpleNamespace
from src.providers.anthropic_adapter import AnthropicAdapter
from src.providers.base import ProviderAuthenticationError, ProviderError
from src.providers.gemini_adapter import GeminiAdapter
from src.providers.openai_adapter import OpenAIAdapter
from src.providers.registry import ProviderRegistry, get_provider_registry


@pytest.fixture(autouse=True)
def no_credentials_or_network(monkeypatch):
    """Use absent test credentials and block sockets for every provider test.

    Inputs: pytest monkeypatch. Returns: no value. Failures: any attempted
    network connection fails immediately; real credential files are never read.
    These are structural offline checks, not live connectivity/quality claims.
    """
    for target in ("src.providers.gemini_adapter.get_gemini_key",
                   "src.providers.openai_adapter.get_openai_key",
                   "src.providers.anthropic_adapter.get_claude_key",
                   "src.providers.anthropic_adapter.get_claude_workspace_id"):
        monkeypatch.setattr(target, lambda: None)
    def forbidden(*args, **kwargs):
        """Tripwire for unintended network traffic from any fake-only test."""
        pytest.fail("Provider tests must not use network connections")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def gemini_transport(monkeypatch):
    """Capture SDK config with official local types and a fake generation client.

    Returns: SDK types, mutable synthetic response state and request observations.
    No client or generation method from the real SDK is executed.
    """
    genai = pytest.importorskip("google.genai")
    from google.genai import types
    state = {"usage": types.GenerateContentResponseUsageMetadata(
        prompt_token_count=10, candidates_token_count=3, total_token_count=13),
        "text": "synthetic response", "finish": types.FinishReason.STOP}
    observed = []
    class FakeClient:
        """Minimal client that records requests without credentials or network."""
        def __init__(self, api_key, http_options):
            """Check only the synthetic marker and single-attempt transport policy."""
            assert api_key == "synthetic"
            assert http_options.retry_options.attempts == 1
            self.http_options = http_options
            self.models = SimpleNamespace(generate_content=self.generate_content)
        def generate_content(self, **kwargs):
            """Return caller-controlled counters and finish status exactly once."""
            observed.append({**kwargs, "http_options": self.http_options})
            return SimpleNamespace(text=state["text"], usage_metadata=state["usage"],
                                   candidates=[SimpleNamespace(finish_reason=state["finish"])])
    monkeypatch.setattr(genai, "Client", FakeClient)
    return types, state, observed


@pytest.mark.parametrize("explicit_none", [False, True])
def test_gemini_default_thinking_preserves_exact_legacy_config(gemini_transport, explicit_none):
    """Neither omitted nor explicit None adds a field or changes the original request."""
    types, _, observed = gemini_transport
    adapter = GeminiAdapter(api_key="synthetic", offline_mode=False,
                            **({"thinking_level": None} if explicit_none else {}))
    adapter.generate("prompt", system_prompt="system")
    expected = types.GenerateContentConfig(temperature=.20, max_output_tokens=4096, system_instruction="system")
    actual = observed[0]["config"]
    assert actual.model_dump_json() == expected.model_dump_json()
    assert actual.model_fields_set == expected.model_fields_set
    assert "thinking_config" not in actual.model_fields_set
    assert adapter.generation_options == {} and adapter.thinking_level is None
    assert observed[0]["model"] == adapter.model_id == "gemini-3.8-flash"
    assert observed[0]["http_options"].timeout == 60000


@pytest.mark.parametrize("level", ["LOW", "medium", "HIGH"])
def test_gemini_explicit_thinking_level_reaches_official_config(gemini_transport, level):
    """Configured tier and caller-owned ceiling reach the unchanged model request."""
    types, _, observed = gemini_transport
    adapter = GeminiAdapter(api_key="synthetic", offline_mode=False, thinking_level=level,
                            max_tokens=16384, timeout_seconds=240)
    adapter.generate("prompt", system_prompt="system")
    config = observed[0]["config"]
    assert isinstance(config.thinking_config, types.ThinkingConfig)
    assert config.thinking_config.thinking_level == types.ThinkingLevel(level.upper())
    assert config.thinking_config.model_fields_set == {"thinking_level"}
    assert config.max_output_tokens == 16384
    assert observed[0]["http_options"].timeout == 240000
    assert adapter.generation_options == {"thinking_level": level.upper()}
    assert len(observed) == 1


def test_gemini_official_enum_and_mutation_are_exposed_to_request_identity(gemini_transport):
    """A fresh settings dict mirrors each actual request, including reset to legacy None."""
    types, _, observed = gemini_transport
    adapter = GeminiAdapter(api_key="synthetic", offline_mode=False, thinking_level=types.ThinkingLevel.MEDIUM)
    view = adapter.generation_options
    view["thinking_level"] = "LOW"
    assert adapter.generation_options == {"thinking_level": "MEDIUM"}
    adapter.generate("first")
    adapter.thinking_level = "low"
    adapter.generate("second")
    adapter.thinking_level = None
    adapter.generate("third")
    assert [r["config"].thinking_config.thinking_level if r["config"].thinking_config else None
            for r in observed] == [types.ThinkingLevel.MEDIUM, types.ThinkingLevel.LOW, None]
    assert adapter.generation_options == {} and "thinking_config" not in observed[-1]["config"].model_fields_set


@pytest.mark.parametrize("invalid", ["", "MINIMAL", "XHIGH", "automatic", " MEDIUM ", 4096, True, {}, []])
def test_gemini_invalid_thinking_level_rejects_before_credentials_or_client(monkeypatch, invalid):
    """Unknown tiers/budgets are never silently dropped, coerced or sent to a provider."""
    def forbidden():
        """Tripwire: invalid configuration must precede credential resolution."""
        pytest.fail("Invalid thinking configuration attempted credential resolution")
    monkeypatch.setattr("src.providers.gemini_adapter.get_gemini_key", forbidden)
    with pytest.raises(ValueError, match="thinking_level"):
        GeminiAdapter(thinking_level=invalid)
    adapter = GeminiAdapter(api_key=None, offline_mode=True, thinking_level="MEDIUM")
    with pytest.raises(ValueError, match="thinking_level"):
        adapter.thinking_level = invalid
    assert adapter.thinking_level == "MEDIUM"


def test_gemini_thoughts_cache_tools_and_official_total_are_preserved(gemini_transport):
    """Synthetic thinking usage is billable output; candidate text is separately counted."""
    types, state, observed = gemini_transport
    state["usage"] = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=47008, candidates_token_count=360, thoughts_token_count=8640,
        tool_use_prompt_token_count=5, total_token_count=56013, cached_content_token_count=700,
        prompt_tokens_details=[types.ModalityTokenCount(modality=types.MediaModality.TEXT, token_count=47008)],
        cache_tokens_details=[types.ModalityTokenCount(modality=types.MediaModality.TEXT, token_count=700)])
    expected = state["usage"].model_dump(mode="json", by_alias=False, exclude_unset=True)
    state.update(text='{"unfinished":', finish=types.FinishReason.MAX_TOKENS)
    adapter = GeminiAdapter(api_key="synthetic", offline_mode=False, thinking_level="MEDIUM", max_tokens=9000)
    result = adapter.generate("prompt")
    assert result.was_truncated and result.content == state["text"] and len(observed) == 1
    assert result.usage.input_tokens == 47013
    assert result.usage.output_tokens == 9000
    assert result.usage.total_tokens == result.usage.input_tokens + result.usage.output_tokens == 56013
    assert result.usage.cached_input_tokens == 700
    assert result.usage.estimated_cost_usd == adapter.estimate_cost(47013, 9000)
    assert result.usage.actual_cost_usd is None
    assert result.usage.raw_usage == expected
    assert result.usage.raw_usage["candidates_token_count"] == 360
    assert result.usage.raw_usage["thoughts_token_count"] == 8640
    state["usage"].thoughts_token_count = 1
    assert result.usage.raw_usage["thoughts_token_count"] == 8640


@pytest.mark.parametrize("optional_counts", [{}, {"thoughts_token_count": None, "cached_content_token_count": None},
                                          {"thoughts_token_count": 0, "tool_use_prompt_token_count": 0}])
def test_gemini_missing_thoughts_are_not_inferred_from_official_total(gemini_transport, optional_counts):
    """Unexplained totals stay visible in raw metadata; missing thinking is not guessed."""
    types, state, _ = gemini_transport
    state["usage"] = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=10, candidates_token_count=3, total_token_count=99, **optional_counts)
    result = GeminiAdapter(api_key="synthetic", offline_mode=False).generate("prompt")
    assert (result.usage.input_tokens, result.usage.output_tokens, result.usage.total_tokens) == (10, 3, 13)
    assert result.usage.raw_usage["total_token_count"] == 99
    assert ("thoughts_token_count" in result.usage.raw_usage) == ("thoughts_token_count" in optional_counts)
    for key, value in optional_counts.items():
        assert result.usage.raw_usage[key] == value


@pytest.mark.parametrize("field,value", [("prompt_token_count", None), ("candidates_token_count", None),
                                        ("thoughts_token_count", -1), ("thoughts_token_count", True),
                                        ("tool_use_prompt_token_count", "5"), ("cached_content_token_count", -1)])
def test_gemini_malformed_usage_fails_without_retry(gemini_transport, field, value):
    """Malformed provider counters fail once instead of producing fabricated accounting."""
    _, state, observed = gemini_transport
    state["usage"] = SimpleNamespace(**{"prompt_token_count": 10, "candidates_token_count": 3, field: value})
    with pytest.raises(ProviderError, match="usage invalid"):
        GeminiAdapter(api_key="synthetic", offline_mode=False).generate("prompt")
    assert len(observed) == 1


def test_gemini_offline_thinking_never_constructs_a_client(monkeypatch):
    """Opt-in configuration is inspectable offline while deterministic legacy output remains unchanged."""
    genai = pytest.importorskip("google.genai")
    def forbidden(*args, **kwargs):
        """Tripwire for accidentally leaving the adapter's offline path."""
        pytest.fail("Offline mode constructed an SDK client")
    monkeypatch.setattr(genai, "Client", forbidden)
    old = GeminiAdapter(api_key=None, offline_mode=True).generate("prompt")
    configured = GeminiAdapter(api_key=None, offline_mode=True, thinking_level="MEDIUM").generate("prompt")
    assert configured.model_dump() == old.model_dump()


def test_gemini_adapter_offline_mode() -> None:
    """Verifies that GeminiAdapter in offline mode emits simulated scholarly output without network calls."""
    adapter = GeminiAdapter(offline_mode=True)
    assert adapter.provider_name == "google"
    assert adapter.supports_prompt_caching is True

    response = adapter.generate(prompt="Explain Narada Sutra 1", system_prompt="You are Narada specialist.")
    assert response.content is not None
    assert "Narada Specialist Exposition" in response.content
    assert response.usage.input_tokens > 0
    assert response.usage.output_tokens > 0


def test_gemini_live_usage_allows_absent_cache_counter(monkeypatch) -> None:
    """A provider's optional null cache count is zero, not a usage validation failure."""
    genai = pytest.importorskip("google.genai")

    class FakeClient:
        """Expose a synthetic SDK response without network traffic."""

        def __init__(self, api_key, http_options):
            """Accept the synthetic credential without retaining it."""
            assert http_options.retry_options.attempts == 1
            assert http_options.timeout == 60000
            self.models = SimpleNamespace(generate_content=self.generate_content)

        def generate_content(self, **kwargs):
            """Return observed prompt/output counts and a null optional cache count."""
            return SimpleNamespace(text="valid response", candidates=[], usage_metadata=SimpleNamespace(
                prompt_token_count=10, candidates_token_count=3,
                cached_content_token_count=None))

    monkeypatch.setattr(genai, "Client", FakeClient)
    response = GeminiAdapter(api_key="synthetic", offline_mode=False).generate("prompt")
    assert response.usage.cached_input_tokens == 0
    assert response.usage.total_tokens == 13


def test_openai_adapter_offline_mode() -> None:
    """Verifies that OpenAIAdapter in offline mode emits simulated analytical output without network calls."""
    adapter = OpenAIAdapter(offline_mode=True)
    assert adapter.provider_name == "openai"
    assert adapter.supports_prompt_caching is True

    response = adapter.generate(prompt="Analyze Shandilya Sutra 1")
    assert response.content is not None
    assert "Scholarly Analysis" in response.content
    assert response.usage.input_tokens > 0


def test_anthropic_adapter_offline_mode() -> None:
    """Verifies that AnthropicAdapter in offline mode emits simulated composition output without network calls."""
    adapter = AnthropicAdapter(offline_mode=True)
    assert adapter.provider_name == "anthropic"
    assert adapter.supports_prompt_caching is True

    response = adapter.generate(prompt="Compose Udyoga Sutra 1")
    assert response.content is not None
    assert "Sutrakar Master Author" in response.content
    assert response.usage.input_tokens > 0


def test_anthropic_live_request_receives_composition_ceiling(monkeypatch) -> None:
    """The larger dispatcher ceiling reaches the unchanged Claude model SDK call."""
    anthropic = pytest.importorskip("anthropic")
    observed = {}

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0
            self.messages = SimpleNamespace(create=self.create)

        def create(self, **kwargs):
            observed.update(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="{}")],
                                   stop_reason="end_turn",
                                   usage=SimpleNamespace(input_tokens=5, output_tokens=2,
                                                         cache_read_input_tokens=0,
                                                         cache_creation_input_tokens=0))

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    adapter = AnthropicAdapter(api_key="synthetic", offline_mode=False,
                               model_id="claude-sonnet-5-5")
    adapter.max_tokens = 16384
    adapter.generate("prompt")
    assert observed["model"] == "claude-sonnet-5-5"
    assert observed["max_tokens"] == 16384


def test_provider_authentication_error_when_online_without_key() -> None:
    """Verifies that attempting live execution without an API key raises ProviderAuthenticationError."""
    adapter = OpenAIAdapter(api_key=None, offline_mode=False)
    with pytest.raises(ProviderAuthenticationError):
        adapter.generate(prompt="Test live prompt")


def test_provider_registry_five_agent_allocations() -> None:
    """Verifies that the registry allocates all five distinct council agents correctly."""
    registry = ProviderRegistry(offline_mode=True)

    agent1 = registry.get_adapter(ProviderRegistry.ROLE_NARADA)
    assert agent1.provider_name == "google"

    agent2 = registry.get_adapter(ProviderRegistry.ROLE_SHANDILYA)
    assert agent2.provider_name == "openai"

    agent3 = registry.get_adapter(ProviderRegistry.ROLE_BHARATIYA_JNANA)
    assert agent3.provider_name == "anthropic"

    agent4 = registry.get_adapter(ProviderRegistry.ROLE_SUTRAKAR)
    assert agent4.provider_name == "anthropic"

    agent5 = registry.get_adapter(ProviderRegistry.ROLE_VALIDATOR)
    assert agent5.provider_name == "openai"


def test_provider_registry_dynamic_model_switch() -> None:
    """Verifies that an agent's underlying provider/model can be switched dynamically."""
    registry = ProviderRegistry(offline_mode=True)
    # Switch Agent 1 to Anthropic
    registry.switch_model(ProviderRegistry.ROLE_NARADA, provider="anthropic", model_id="claude-3-5-sonnet-20241022")
    new_agent1 = registry.get_adapter(ProviderRegistry.ROLE_NARADA)
    assert new_agent1.provider_name == "anthropic"
    assert new_agent1.model_id == "claude-3-5-sonnet-20241022"

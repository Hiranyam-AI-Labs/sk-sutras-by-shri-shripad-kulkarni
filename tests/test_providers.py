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
from types import SimpleNamespace
from src.providers.anthropic_adapter import AnthropicAdapter
from src.providers.base import ProviderAuthenticationError
from src.providers.gemini_adapter import GeminiAdapter
from src.providers.openai_adapter import OpenAIAdapter
from src.providers.registry import ProviderRegistry, get_provider_registry


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

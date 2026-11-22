"""
================================================================================
Test Module: tests.test_credentials
Author: Hiranyam AI Labs (https://hiranyamai.com/)
Project: SK Sutras - by Shri Shripad Kulkarni
Description: Unit tests verifying that API keys are loaded independently from
             their separate, dedicated credential files (Claude, Gemini, OpenAI)
             without hardcoding or cross-contamination.
================================================================================
"""

import pytest
import src.credentials as credentials
from src.credentials import (
    get_api_key_for_provider,
    get_claude_key,
    get_gemini_key,
    get_openai_key,
    sync_keys_to_environment,
    verify_keys_present,
)


@pytest.fixture(autouse=True)
def isolated_key_files(tmp_path, monkeypatch):
    """Use temporary synthetic files and restore environment after each test.

    Inputs are pytest fixtures; returns provider markers for assertions. Never
    reads real credentials. A failure indicates loader behavior, not deployment
    readiness; inspect temporary paths without printing production secrets.
    """
    for variable in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY", "GOOGLE_API_KEY",
                     "GEMINI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    markers = {}
    for provider in ("claude", "gemini", "openai"):
        marker = provider + "-unit-test-only"
        path = tmp_path / (provider + "_key.txt")
        path.write_text(' "' + marker + '"\n', encoding="utf-8")
        monkeypatch.setattr(credentials, provider.upper() + "_KEY_PATHS", [path])
        markers[provider] = marker
    # Record environment restoration before the production sync function writes.
    for variable in ("ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(variable, "")
    return markers


def test_separate_key_files_loaded(isolated_key_files) -> None:
    """Verifies that each individual model key is loaded from its own separate file."""
    claude_key = get_claude_key()
    gemini_key = get_gemini_key()
    openai_key = get_openai_key()

    # All three must be present and non-empty
    assert claude_key is not None and len(claude_key) > 10
    assert gemini_key is not None and len(gemini_key) > 10
    assert openai_key is not None and len(openai_key) > 10

    # The three keys must be strictly separate and unique
    assert claude_key != gemini_key
    assert claude_key != openai_key
    assert gemini_key != openai_key

    # Verify exact separate fixture values, not vendor-specific token formats.
    assert claude_key == isolated_key_files["claude"]
    assert gemini_key == isolated_key_files["gemini"]
    assert openai_key == isolated_key_files["openai"]


def test_provider_dispatch() -> None:
    """Verifies that generic provider dispatch returns the corresponding separate key."""
    assert get_api_key_for_provider("anthropic") == get_claude_key()
    assert get_api_key_for_provider("claude") == get_claude_key()
    assert get_api_key_for_provider("google") == get_gemini_key()
    assert get_api_key_for_provider("gemini") == get_gemini_key()
    assert get_api_key_for_provider("openai") == get_openai_key()
    assert get_api_key_for_provider("unknown_provider") is None


def test_verify_keys_present() -> None:
    """Verifies that verify_keys_present reports true for all three separate files."""
    status = verify_keys_present()
    assert status["claude"] is True
    assert status["gemini"] is True
    assert status["openai"] is True


def test_sync_keys_to_environment() -> None:
    """Verifies that syncing keys to environment injects keys into os.environ."""
    import os
    synced = sync_keys_to_environment(override=True)
    assert synced["claude"] is True
    assert synced["gemini"] is True
    assert synced["openai"] is True
    assert os.getenv("ANTHROPIC_API_KEY") == get_claude_key()
    assert os.getenv("GOOGLE_API_KEY") == get_gemini_key()
    assert os.getenv("OPENAI_API_KEY") == get_openai_key()

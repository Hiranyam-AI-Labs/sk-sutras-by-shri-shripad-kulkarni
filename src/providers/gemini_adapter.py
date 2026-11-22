"""
================================================================================
Module: src.providers.gemini_adapter
Author: Hiranyam AI Labs (https://hiranyamai.com/)
Project: SK Sutras - by Shri Shripad Kulkarni
Description: Adapter for Google Gemini models (Gemini 1.5 Pro) designated for
             Agent 1 (Narada Bhakti Sutra Specialist). Supports prompt caching,
             usage extraction, token estimation, and offline development mode.
================================================================================
"""

import os
import warnings
from copy import deepcopy
from typing import Any, Dict, Optional

# Suppress Python version lifecycle and package deprecation warnings for 100% clean logs
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from src.credentials import get_gemini_key
from src.providers.base import (
    BaseLLMAdapter,
    ProviderAuthenticationError,
    ProviderError,
    ProviderResponse,
    ProviderUsage,
)

_UNSET_KEY = object()


def _usage_payload(metadata: Any) -> Dict[str, Any]:
    """Purpose: retain official usage counters without inferring hidden thinking.

    Inputs: SDK usage model, dictionary or attribute-based offline test double.
    Returns: detached metadata with SDK snake-case names, including explicitly
    supplied nulls and nested modality/cache details. Failures: malformed or
    missing metadata raises ValueError. Debug: inspect this metadata, not final
    text length, for reported thought usage; absent counts remain absent.
    """
    if callable(getattr(metadata, "model_dump", None)):
        value = metadata.model_dump(mode="json", by_alias=False, exclude_unset=True)
    elif isinstance(metadata, dict):
        value = metadata
    elif hasattr(metadata, "__dict__"):
        value = vars(metadata)
    else:
        raise ValueError("Gemini provider usage unavailable")
    if not isinstance(value, dict):
        raise ValueError("Gemini provider usage malformed")
    return deepcopy(value)


def _token_count(usage: Dict[str, Any], field: str, *, optional: bool = False) -> int:
    """Purpose: read a nonnegative reported counter for normalized accounting.

    Inputs: preserved usage dictionary, SDK field name and optional-count flag.
    Returns: integer count; absent/null optional fields add zero without altering
    raw metadata. Failures: missing required, boolean, negative or noninteger
    counts raise ValueError. Debug: missing thoughts are not evidence of zero
    thinking and are never reconstructed from the provider's total.
    """
    value = usage.get(field)
    if optional and value is None:
        return 0
    if type(value) is not int or value < 0:
        raise ValueError(f"Gemini provider usage invalid: {field}")
    return value


class GeminiAdapter(BaseLLMAdapter):
    """
    ----------------------------------------------------------------------------
    Class: GeminiAdapter
    ----------------------------------------------------------------------------
    Purpose:
        Implements Google Gemini API communication for the Narada Specialist Agent.
        Provides prompt caching integration, token consumption extraction, and
        safe offline development modes preventing unapproved live API calls.
        Reads the API key from its separate dedicated credential file (keys/gemini_key.txt).
    ----------------------------------------------------------------------------
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        api_key: Any = _UNSET_KEY,
        temperature: float = 0.20,
        max_tokens: int = 4096,
        timeout_seconds: float = 60.0,
        offline_mode: Optional[bool] = None,
        thinking_level: Optional[str] = None,
    ) -> None:
        """
        ------------------------------------------------------------------------
        Method: __init__
        ------------------------------------------------------------------------
        Purpose:
            Initializes the Google Gemini adapter with configurable model IDs
            and safe key retrieval from keys/gemini_key.txt.
            thinking_level accepts LOW/MEDIUM/HIGH (case-insensitive) or None.
            None preserves the exact legacy request config: no thinking_config.
            Explicit levels use the official SDK ThinkingConfig; MEDIUM is a
            reasoning tier, not a fixed numeric thought-token guarantee.
            Gemini 3.8 Flash already defaults to MEDIUM at the provider; making
            MEDIUM explicit is not by itself a reduction in thinking or a
            demonstrated remedy for truncation. Output headroom is caller-owned.
            Configure via this argument or the thinking_level property. Caller
            request identities must bind generation_options when nonempty.
            Invalid levels fail before credentials or client construction.
        ------------------------------------------------------------------------
        """
        self.thinking_level = thinking_level
        resolved_model = model_id or os.getenv("GEMINI_MODEL_ID", "gemini-3.8-flash")
        resolved_key = get_gemini_key() if api_key is _UNSET_KEY else api_key
        # In this phase, offline mode defaults to True if credentials are absent or explicitly set
        resolved_offline = (
            offline_mode
            if offline_mode is not None
            else (os.getenv("OFFLINE_MODE", "true").lower() == "true" or not resolved_key)
        )

        super().__init__(
            model_id=resolved_model,
            api_key=resolved_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            offline_mode=resolved_offline,
        )

    @property
    def thinking_level(self) -> Optional[str]:
        """Return the canonical explicit Gemini thinking tier, or legacy None."""
        return self._thinking_level

    @thinking_level.setter
    def thinking_level(self, value: Optional[str]) -> None:
        """Validate an opt-in LOW/MEDIUM/HIGH tier without SDK/key access.

        Inputs: tier string (also an official string enum) or None. Returns:
        None after storing a canonical uppercase value. Failures: invalid types
        or tiers raise ValueError before mutation. Debug: numeric budgets and
        unsupported model-specific tiers are not equivalent to this setting.
        """
        normalized = value.upper() if isinstance(value, str) else value
        if normalized is not None and (not isinstance(normalized, str)
                                       or normalized not in {"LOW", "MEDIUM", "HIGH"}):
            raise ValueError("Gemini thinking_level must be None, LOW, MEDIUM or HIGH")
        self._thinking_level = normalized

    @property
    def generation_options(self) -> Dict[str, str]:
        """Return actual nondefault generation settings for caller request hashes.

        Inputs: current adapter setting. Returns: a fresh empty dict for legacy
        None, otherwise {'thinking_level': canonical tier}. No I/O or failures.
        Debug: bind this per request, not into old global checkpoint config;
        callers serialize setting changes and dispatch under their existing lock.
        """
        return {} if self.thinking_level is None else {"thinking_level": self.thinking_level}

    @property
    def provider_name(self) -> str:
        """Returns the provider identifier string."""
        return "google"

    @property
    def supports_prompt_caching(self) -> bool:
        """Gemini 1.5 Pro natively supports context caching for large corpora."""
        return True

    @property
    def supports_batch_api(self) -> bool:
        """Google Vertex/Gemini Batch Prediction interface support."""
        return True

    def estimate_tokens(self, text: str) -> int:
        """
        ------------------------------------------------------------------------
        Method: estimate_tokens
        ------------------------------------------------------------------------
        Purpose:
            Provides a safe offline estimation of token count. For Sanskrit and
            Devanagari text, UTF-8 character density is approximately 1 token
            per 2-3 characters.
        ------------------------------------------------------------------------
        """
        if not text:
            return 0
        # For Devanagari text, tokens roughly equal len(text) / 2.5
        return max(1, int(len(text) / 2.5))

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        cached_context: Optional[str] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """
        ------------------------------------------------------------------------
        Method: generate
        ------------------------------------------------------------------------
        Purpose:
            Generates text completions. In offline mode, constructs a structured
            offline analytical response without making external network calls.
        ------------------------------------------------------------------------
        """
        if self.offline_mode:
            # Deterministic, scholarly mock response for offline verification
            input_toks = self.estimate_tokens((system_prompt or "") + prompt)
            output_toks = 180
            usage = ProviderUsage(
                input_tokens=input_toks,
                output_tokens=output_toks,
                cached_input_tokens=self.estimate_tokens(cached_context or "") if cached_context else 0,
                total_tokens=input_toks + output_toks,
                estimated_cost_usd=self.estimate_cost(input_toks, output_toks),
                currency="USD",
                raw_usage={"mode": "offline_simulated"},
            )
            mock_content = (
                "[Google Gemini / Narada Specialist Exposition - Offline Review Mode]\n"
                "Sutra analysis completed with fidelity to Devarshi Narada's canonical tradition.\n"
                "Emphasizes ecstatic devotion, self-surrender, and supreme love (Prema-Rupa)."
            )
            return ProviderResponse(
                content=mock_content,
                usage=usage,
                model_id=self.model_id,
                provider=self.provider_name,
                finish_reason="stop",
            )

        if not self.api_key:
            raise ProviderAuthenticationError(
                message="Google API key missing or unconfigured.",
                provider=self.provider_name,
                model_id=self.model_id,
            )

        # When authorized live mode is triggered by owner
        try:
            # Modern official Google GenAI SDK (google-genai)
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(
                    timeout=max(1, int(self.timeout_seconds * 1000)),
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            config_options = dict(
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
                system_instruction=system_prompt if system_prompt else None,
            )
            if self.thinking_level is not None:
                # Official Gemini 3 control; no numeric thinking_budget or thought
                # summaries. Default None does not add even a null config field.
                # https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/thinking
                config_options["thinking_config"] = types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel(self.thinking_level))
            config = types.GenerateContentConfig(**config_options)
            response = client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=config,
            )

            raw_usage = _usage_payload(getattr(response, "usage_metadata", None))
            prompt_toks = _token_count(raw_usage, "prompt_token_count")
            candidate_toks = _token_count(raw_usage, "candidates_token_count")
            thought_toks = _token_count(raw_usage, "thoughts_token_count", optional=True)
            tool_toks = _token_count(raw_usage, "tool_use_prompt_token_count", optional=True)
            cached_toks = _token_count(raw_usage, "cached_content_token_count", optional=True)
            # Generic completion accounting includes reported thoughts, like
            # reasoning-token accounting elsewhere. Visible candidate count,
            # thoughts, tool prompts and official total remain separate in raw_usage.
            # Keep normalized total=input+output; never guess thoughts from an
            # unexplained official total. Missing optional counters add no tokens.
            # https://ai.google.dev/api/generate-content#UsageMetadata
            input_toks = prompt_toks + tool_toks
            output_toks = candidate_toks + thought_toks

            usage = ProviderUsage(
                input_tokens=input_toks,
                output_tokens=output_toks,
                cached_input_tokens=cached_toks,
                total_tokens=input_toks + output_toks,
                estimated_cost_usd=self.estimate_cost(input_toks, output_toks),
                currency="USD",
                raw_usage=raw_usage,
            )
            cand_finish = "stop"
            if hasattr(response, "candidates") and response.candidates:
                cand_finish = str(getattr(response.candidates[0], "finish_reason", "stop")).lower()

            return ProviderResponse(
                content=response.text or "",
                usage=usage,
                model_id=self.model_id,
                provider=self.provider_name,
                finish_reason=cand_finish,
                is_truncated=("max_tokens" in cand_finish or "length" in cand_finish),
            )
        except Exception as exc:
            raise ProviderError(
                message=f"Gemini generation failed: {str(exc)}",
                provider=self.provider_name,
                model_id=self.model_id,
                raw_error=exc,
            ) from exc

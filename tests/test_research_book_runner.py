"""Offline runner/SDK contracts, with no provider or credential-module imports.

Load production helper definitions directly from their AST because importing the
live runner also imports credential wiring. SDK extraction tests execute the
actual adapter generate methods against fake SDK modules, never a real client.
These are response-shape tests, not evidence of live provider availability.
"""

import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_definitions(relative, names, namespace):
    """Execute named production definitions only; exclude import-time wiring."""
    filename = ROOT / relative
    source = ast.parse(filename.read_text(encoding="utf-8"), filename=str(filename))
    selected = [node for node in source.body
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    assert {node.name for node in selected} == set(names)
    tree = ast.Module(body=[ast.ImportFrom(module="__future__", names=[
        ast.alias(name="annotations")], level=0), *selected], type_ignores=[])
    exec(compile(ast.fix_missing_locations(tree), str(filename), "exec"), namespace)
    return namespace


@pytest.fixture
def helpers():
    """Load current runner helpers without importing providers or credentials."""
    return load_definitions("scripts/run_research_book.py",
                            {"complete_entry", "prompt_payload"}, {"deepcopy": deepcopy})


@pytest.fixture
def composition():
    """Return a model answer and a canonical packet with nested frozen evidence."""
    cases = [{"case_id": kind, "kind": kind, "entity": "Verified entity",
              "text_mr": "तपासलेला प्रसंग", "source_title": "Canonical source",
              "url": f"https://example.org/{kind}", "metadata": {"page": [1]}}
             for kind in ("positive", "caution")]
    payload = {"sources": {"examples": cases}, "number": 1,
               "brief": {"id": "entry-1", "chapter": "धोरण"}, "used_case_ids": ["old-case"]}
    answer = {"case_ids": ["positive", "caution"], "id": "invented",
              "number": 99, "chapter": "invented", "examples": [{"text_mr": "fiction"}],
              "new_sutra": "उद्यमेन विवेकः", "exposition": ["मूळ विवेचन"]}
    return answer, payload


def test_complete_entry_replaces_generated_facts_and_identity(helpers, composition):
    """Only canonical identities/cases survive, while generated prose is retained."""
    answer, payload = composition
    before = deepcopy(composition)
    result = helpers["complete_entry"](answer, payload)
    assert (result["id"], result["number"], result["chapter"]) == ("entry-1", 1, "धोरण")
    assert result["examples"] == payload["sources"]["examples"]
    assert result["new_sutra"] == answer["new_sutra"]
    assert result["exposition"] == answer["exposition"]
    assert composition == before
    result["examples"][0]["metadata"]["page"].append(2)
    result["exposition"].append("बदल")
    assert composition == before


@pytest.mark.parametrize("selection", [None, [], ["caution", "positive"],
                                        ["positive", "positive"], ["positive", "invented"],
                                        ["positive", "caution", "extra"], "positive,caution"])
def test_complete_entry_rejects_changed_case_selection(helpers, composition, selection):
    """Missing, reordered, duplicated or invented cases cannot be silently accepted."""
    answer, payload = composition
    answer["case_ids"] = selection
    with pytest.raises(ValueError, match="case_ids"):
        helpers["complete_entry"](answer, payload)


@pytest.mark.parametrize("answer", [None, [], [["case_ids", ["positive", "caution"]]], "{}"])
def test_complete_entry_requires_an_object(helpers, composition, answer):
    """A coercible list of pairs is still not a provider JSON-object response."""
    with pytest.raises(ValueError, match="JSON object"):
        helpers["complete_entry"](answer, composition[1])


def test_prompt_preserves_canonical_evidence_and_peer_arguments(helpers, composition):
    """Prompt compaction removes only the global occupancy audit field."""
    payload = composition[1]
    payload["discussion"] = {"reply": {"researcher": {
        "answers": {"sutrakar": {"1": "Literal source evidence"}}}}}
    before = deepcopy(payload)
    result = helpers["prompt_payload"](payload)
    assert result == {key: value for key, value in before.items() if key != "used_case_ids"}
    assert payload == before


def test_entry_prompt_retains_only_current_batch_evidence_without_mutation(helpers, composition):
    """Keep the current entry's peer arguments while omitting other-entry bulk."""
    payload = composition[1]
    payload["sources_by_entry"] = {"1": payload["sources"], "2": {"references": []}}
    payload["discussion"] = {
        "_batch": {"batch_id": "group-1"},
        "position": {"researcher": {"positions": {"1": {"thesis": "current"}, "2": {"thesis": "other"}}}},
        "reply": {"researcher": {"answers": {"sutrakar": {"1": "current answer", "2": "other answer"}}}},
    }
    before = deepcopy(payload)
    result = helpers["prompt_payload"](payload)
    assert result["sources"] == before["sources"]
    assert "sources_by_entry" not in result and "_batch" not in result["discussion"]
    assert result["discussion"]["position"]["researcher"]["positions"] == {"1": {"thesis": "current"}}
    assert result["discussion"]["reply"]["researcher"]["answers"] == {"sutrakar": {"1": "current answer"}}
    assert payload == before


@pytest.fixture
def response_contract(monkeypatch):
    """Load the actual pydantic response classes without provider package startup."""
    name = "_offline_research_response_contract"
    spec = importlib.util.spec_from_file_location(name, ROOT / "src/providers/base.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("provider,model,adapter_file,adapter_class", [
    ("openai", "gpt-4o", "openai_adapter.py", "OpenAIAdapter"),
    ("anthropic", "claude-sonnet-5-5", "anthropic_adapter.py", "AnthropicAdapter"),
    ("google", "gemini-3.8-flash", "gemini_adapter.py", "GeminiAdapter"),
])
@pytest.mark.parametrize("truncated", [False, True])
def test_actual_adapter_extracts_sdk_text_usage_and_model_binding(
        monkeypatch, response_contract, provider, model, adapter_file, adapter_class, truncated):
    """Exercise production SDK extraction against fake chat/message/genai responses.

    The returned model ID is the configured adapter ID; this does not attest to
    server-resolved model identity. Every SDK client is replaced before generate.
    """
    text = '{"new_sutra":"उद्यमेन विवेकः"}'
    calls, clients = [], []

    def create(**kwargs):
        """Record exactly one SDK request and return its provider-shaped fixture."""
        calls.append(kwargs)
        if provider == "openai":
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=text), finish_reason="length" if truncated else "stop")],
                usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7))
        if provider == "anthropic":
            return SimpleNamespace(content=[SimpleNamespace(type="thinking", thinking="not output"),
                                           SimpleNamespace(type="text", text=text[:10]),
                                           SimpleNamespace(type="text", text=text[10:])],
                                   stop_reason="max_tokens" if truncated else "end_turn",
                                   usage=SimpleNamespace(input_tokens=11, output_tokens=7))
        return SimpleNamespace(text=text, usage_metadata=SimpleNamespace(
            prompt_token_count=11, candidates_token_count=7),
            candidates=[SimpleNamespace(finish_reason="MAX_TOKENS" if truncated else "STOP")])

    def client(**kwargs):
        """Replace SDK construction; use only inert call-recording objects."""
        clients.append(kwargs)
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
                               messages=SimpleNamespace(create=create),
                               models=SimpleNamespace(generate_content=create))

    for name, attribute in (("openai", "OpenAI"), ("anthropic", "Anthropic")):
        fake = ModuleType(name)
        setattr(fake, attribute, client)
        monkeypatch.setitem(sys.modules, name, fake)
    google, genai, types = ModuleType("google"), ModuleType("google.genai"), ModuleType("google.genai.types")
    types.HttpOptions = types.HttpRetryOptions = types.GenerateContentConfig = SimpleNamespace
    genai.Client, genai.types, google.genai = client, types, genai
    for name, module in (("google", google), ("google.genai", genai), ("google.genai.types", types)):
        monkeypatch.setitem(sys.modules, name, module)

    filename = ROOT / "src/providers" / adapter_file
    tree = ast.parse(filename.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == adapter_class)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "generate")
    namespace = {key: getattr(response_contract, key) for key in
                 ("ProviderResponse", "ProviderUsage", "ProviderError", "ProviderAuthenticationError")}
    body = ast.Module(body=[ast.ImportFrom(module="__future__", names=[
        ast.alias(name="annotations")], level=0), method], type_ignores=[])
    exec(compile(ast.fix_missing_locations(body), str(filename), "exec"), namespace)
    adapter = SimpleNamespace(model_id=model, provider_name=provider, offline_mode=False,
                              api_key="offline-test-placeholder", workspace_id=None, timeout_seconds=1,
                              max_tokens=14000, temperature=0.2, estimate_cost=lambda *_: 0.0)
    response = namespace["generate"](adapter, "test prompt", "test system")
    assert isinstance(response, response_contract.ProviderResponse)
    assert response.content == text
    assert json.loads(response.content)["new_sutra"] == "उद्यमेन विवेकः"
    assert (response.model_id, response.provider) == (model, provider)
    assert (response.usage.input_tokens, response.usage.output_tokens, response.usage.total_tokens) == (11, 7, 18)
    assert response.was_truncated is truncated
    assert len(calls) == len(clients) == 1
    assert calls[0]["model"] == model
    if provider == "google":
        assert clients[0]["http_options"].retry_options.attempts == 1
        assert calls[0]["config"].max_output_tokens == 14000
    else:
        assert clients[0]["max_retries"] == 0
        assert calls[0]["max_tokens"] == 14000

"""Actual runner routes all five roles through injected dispatch with no paid calls."""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from scripts.run_dynamic_live_council import DynamicLiveCouncilRunner
from src.agents.acceptance_policy import GATE_NAMES
from src.database.example_registry import ExampleRegistry
from src.orchestration.review_store import ReviewStore
from src.providers.dispatch import BudgetedDispatcher
from tests.test_council_service import make_draft


class FakeVector:
    """Return one candidate with the production query result shape."""

    def query_similar_sutras(self, query_text, top_k):
        """Return a deterministic Shandilya reference for the supplied source."""
        return [{"metadata": {"sutra_no": "1"}}]


class FakeDispatch:
    """Capture role dispatch and supply only structured synthetic responses."""

    def __init__(self):
        """Start a zero-call fake; no credentials or network are used."""
        self.calls = []

    def call(self, role, prompt, system_prompt):
        """Answer each role and stage with a deterministic JSON object."""
        payload = json.loads(prompt)
        self.calls.append((role, payload))
        if role == "sutrakar_master":
            mode = payload["mode"]
            data = ({"accepted": True} if mode == "arbitrate" else
                    {"findings": ["independent"], "challenges": ["check source"]} if mode == "consult"
                    else make_draft())
        elif role == "bharatiya_jnana_specialist":
            data = {"bridge": "Bridge", "findings": ["documented"]}
        elif role == "independent_validator":
            data = {"gates": {name: {"status": "PASS", "evidence": "Synthetic inspection"}
                              for name in GATE_NAMES}}
        else:
            data = {"analysis": "Synthetic source review"}
        return SimpleNamespace(content=json.dumps(data, ensure_ascii=False))


def test_actual_runner_uses_five_roles_and_never_auto_approves():
    """One candidate reaches human-review state while all calls traverse dispatch."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        source = path / "doc.txt"
        source.write_text("source ethics business passage", encoding="utf-8")
        dispatch = FakeDispatch()
        examples = ExampleRegistry(path / "examples.db")
        examples.register("Person A", "PERSON", "Record A")
        runner = DynamicLiveCouncilRunner(
            dispatcher=dispatch, vector_store=FakeVector(),
            review_store=ReviewStore(path / "review.db"), example_registry=examples,
            narada_sutras=[{"sutra_no": 1, "sanskrit": "source ethics"}],
            shandilya_sutras=[{"sutra_no": 1, "sanskrit": "matching source"}],
            source_paths={"DOC-01": source})
        outcome = runner.execute_live_council(1)
        assert outcome["status"] == "HUMAN_REVIEW_PENDING"
        assert outcome["units"][0]["status"] == "HUMAN_REVIEW_PENDING"
        assert {role for role, _ in dispatch.calls} == {
            "narada_specialist", "shandilya_specialist", "bharatiya_jnana_specialist",
            "sutrakar_master", "independent_validator"}
        assert len([1 for role, _ in dispatch.calls if role == "bharatiya_jnana_specialist"]) == 2


def test_requested_shortfall_is_explicit():
    """An exhausted source corpus cannot report a requested ten as completed."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        source = path / "doc.txt"
        source.write_text("source ethics business passage", encoding="utf-8")
        examples = ExampleRegistry(path / "examples.db")
        examples.register("Person A", "PERSON", "Record A")
        runner = DynamicLiveCouncilRunner(
            dispatcher=FakeDispatch(), vector_store=FakeVector(),
            review_store=ReviewStore(path / "review.db"), example_registry=examples,
            narada_sutras=[{"sutra_no": 1, "sanskrit": "source ethics"}],
            shandilya_sutras=[{"sutra_no": 1, "sanskrit": "matching source"}],
            source_paths={"DOC-01": source})
        assert runner.execute_live_council(10)["status"] == "PARTIAL_BLOCKED"


def test_budget_preflight_blocks_before_first_role_call():
    """A missing role-model rate prevents every provider invocation."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        source = path / "doc.txt"
        source.write_text("source ethics business passage", encoding="utf-8")

        class Adapter:
            """One role's non-network model metadata for preflight."""
            provider_name, model_id, max_tokens = "google", "gemini-3.8-flash", 100

        class Registry:
            """Return configured metadata while recording no external calls."""
            calls = 0

            def get_adapter(self, role):
                """Return one known model metadata object for every role."""
                self.calls += 1
                return Adapter()

        role_registry = Registry()
        dispatch = BudgetedDispatcher(role_registry, {}, 1, 100)
        runner = DynamicLiveCouncilRunner(
            dispatcher=dispatch, vector_store=FakeVector(),
            review_store=ReviewStore(path / "review.db"),
            example_registry=ExampleRegistry(path / "examples.db"),
            narada_sutras=[{"sutra_no": 1, "sanskrit": "source ethics"}],
            shandilya_sutras=[{"sutra_no": 1, "sanskrit": "matching source"}],
            source_paths={"DOC-01": source})
        import pytest
        with pytest.raises(ValueError, match="Missing dated price"):
            runner.execute_live_council(1)
        assert dispatch.calls == 0
        assert dispatch.audit == []

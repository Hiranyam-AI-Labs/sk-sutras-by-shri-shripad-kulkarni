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
from tests.test_council_service import make_draft, register_case_examples


class FakeVector:
    """Return one candidate with the production query result shape."""

    def query_similar_sutras(self, query_text, top_k):
        """Return a deterministic Shandilya reference for the supplied source."""
        return [{"metadata": {"sutra_no": "1"}}]


class FakeDispatch:
    """Capture role dispatch and supply only structured synthetic responses."""

    def __init__(self, fenced_roles=()):
        """Start a zero-call fake; optionally wrap role JSON in code fences."""
        self.calls = []
        self.output_ceilings = []
        self.fenced_roles = set(fenced_roles)

    def call(self, role, prompt, system_prompt, **kwargs):
        """Answer each role and stage with a deterministic JSON object."""
        payload = json.loads(prompt)
        self.calls.append((role, payload))
        self.output_ceilings.append((role, payload.get("mode"), kwargs.get("max_output_tokens")))
        if role == "sutrakar_master":
            mode = payload["mode"]
            data = ({"accepted": True, "sutra_no": "1", "reason": "substantiated"} if mode == "arbitrate" else
                    {"findings": ["independent"], "challenges": ["check source"]} if mode == "consult"
                    else make_draft())
        elif role == "bharatiya_jnana_specialist":
            data = {"bridge": "Bridge", "findings": ["documented"]}
        elif role == "independent_validator":
            data = {"gates": {name: {"status": "PASS", "evidence": "Synthetic inspection"}
                              for name in GATE_NAMES}, "findings": []}
        else:
            data = ({"thesis": "Synthetic source review", "source_reference": "Narada 1"}
                    if role == "narada_specialist" else
                    {"review": "Synthetic candidate review", "preferred_sutra_no": "1",
                     "rejected_reasons": []})
        content = json.dumps(data, ensure_ascii=False)
        return SimpleNamespace(content=f"```json\n{content}\n```" if role in self.fenced_roles else content, was_truncated=False)


def test_actual_runner_uses_five_roles_and_never_auto_approves():
    """One candidate reaches human-review state while all calls traverse dispatch."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        source = path / "doc.txt"
        source.write_text("source ethics business passage", encoding="utf-8")
        dispatch = FakeDispatch()
        examples = ExampleRegistry(path / "examples.db")
        register_case_examples(examples)
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
        assert ("sutrakar_master", "compose", 16384) in dispatch.output_ceilings
        assert len([1 for role, _ in dispatch.calls if role == "bharatiya_jnana_specialist"]) == 2


def test_precomposition_checkpoint_replays_only_exact_source_request():
    """A restarted run reuses validated output; a source edit requires fresh dispatch."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        source = path / "source.txt"
        source.write_text("first source", encoding="utf-8")
        dispatch = FakeDispatch()
        review = ReviewStore(path / "review.db")

        def runner():
            return DynamicLiveCouncilRunner(
                dispatcher=dispatch, vector_store=FakeVector(), review_store=review,
                example_registry=ExampleRegistry(path / "examples.db"),
                narada_sutras=[], shandilya_sutras=[], source_paths={"DOC-01": source},
                run_id="checkpoint-run")

        payload = {"source": {"sutra_no": 1, "sanskrit": "first source"}}
        first = runner()._json_role("narada_specialist", payload)
        assert runner()._json_role("narada_specialist", payload) == first
        assert len(dispatch.calls) == 1
        source.write_text("revised source", encoding="utf-8")
        runner()._json_role("narada_specialist", payload)
        assert len(dispatch.calls) == 2


def test_requested_shortfall_is_explicit():
    """An exhausted source corpus cannot report a requested ten as completed."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        source = path / "doc.txt"
        source.write_text("source ethics business passage", encoding="utf-8")
        examples = ExampleRegistry(path / "examples.db")
        register_case_examples(examples)
        runner = DynamicLiveCouncilRunner(
            dispatcher=FakeDispatch(), vector_store=FakeVector(),
            review_store=ReviewStore(path / "review.db"), example_registry=examples,
            narada_sutras=[{"sutra_no": 1, "sanskrit": "source ethics"}],
            shandilya_sutras=[{"sutra_no": 1, "sanskrit": "matching source"}],
            source_paths={"DOC-01": source})
        assert runner.execute_live_council(10)["status"] == "PARTIAL_BLOCKED"


def test_fenced_role_json_is_parsed_without_weakening_required_fields():
    """Provider markdown fences around complete JSON do not abort the council."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        source = path / "doc.txt"
        source.write_text("source ethics business passage", encoding="utf-8")
        examples = ExampleRegistry(path / "examples.db")
        register_case_examples(examples)
        runner = DynamicLiveCouncilRunner(
            dispatcher=FakeDispatch(fenced_roles={"bharatiya_jnana_specialist"}),
            vector_store=FakeVector(), review_store=ReviewStore(path / "review.db"),
            example_registry=examples,
            narada_sutras=[{"sutra_no": 1, "sanskrit": "source ethics"}],
            shandilya_sutras=[{"sutra_no": 1, "sanskrit": "matching source"}],
            source_paths={"DOC-01": source})
        assert runner.execute_live_council(1)["qualifying"] == 1


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


def test_iks_packet_uses_vector_ids_verified_against_local_corpus():
    """The live researcher receives IKS passages from indexed source IDs."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        source, corpus = path / "doc.txt", path / "iks.json"
        source.write_text("source ethics business passage", encoding="utf-8")
        corpus.write_text(json.dumps([{"id": "iks-1", "tradition": "Yoga",
                                      "section": "one", "verse_no": "2",
                                      "sanskrit": "सत्यं", "english_meaning": "truth"}]), encoding="utf-8")

        class Collection:
            """Return the one test ID from a local vector query."""

            def count(self):
                """Report an indexed entry."""
                return 1

            def query(self, query_texts, n_results):
                """Return the requested semantic ID shape."""
                return {"ids": [["iks-1"]]}

        class Client:
            """Expose only the production IKS collection name."""

            def get_collection(self, name):
                """Reject an unexpected collection identity."""
                assert name == "iks_canonical_library"
                return Collection()

        vector = FakeVector()
        vector.client = Client()
        dispatch = FakeDispatch()
        examples = ExampleRegistry(path / "examples.db")
        register_case_examples(examples)
        runner = DynamicLiveCouncilRunner(
            dispatcher=dispatch, vector_store=vector,
            review_store=ReviewStore(path / "review.db"), example_registry=examples,
            narada_sutras=[{"sutra_no": 1, "sanskrit": "source ethics"}],
            shandilya_sutras=[{"sutra_no": 1, "sanskrit": "matching source"}],
            source_paths={"DOC-01": source, "IKS": corpus})
        assert runner.execute_live_council(1)["qualifying"] == 1
        research = [payload for role, payload in dispatch.calls
                    if role == "bharatiya_jnana_specialist"]
        assert any(p["source_id"] == "IKS:iks-1" for p in research[0]["passages"])


def test_restart_reuses_completed_unit_without_new_provider_calls():
    """A second process with the same run ID cannot replay an eligible chapter."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        source = path / "doc.txt"
        source.write_text("source ethics business passage", encoding="utf-8")
        examples = ExampleRegistry(path / "examples.db")
        register_case_examples(examples)
        first_dispatch = FakeDispatch()
        args = dict(vector_store=FakeVector(), review_store=ReviewStore(path / "review.db"),
                    example_registry=examples,
                    narada_sutras=[{"sutra_no": 1, "sanskrit": "source ethics"}],
                    shandilya_sutras=[{"sutra_no": 1, "sanskrit": "matching source"}],
                    source_paths={"DOC-01": source}, run_id="pilot-one")
        assert DynamicLiveCouncilRunner(dispatcher=first_dispatch, **args).execute_live_council(1)["qualifying"] == 1
        restarted_dispatch = FakeDispatch()
        outcome = DynamicLiveCouncilRunner(dispatcher=restarted_dispatch, **args).execute_live_council(1)
        assert outcome["qualifying"] == 1
        assert restarted_dispatch.calls == []
        assert args["review_store"].latest_state("UDYAM-1")["version"] == 1


def test_composition_continuation_and_exact_checkpoint(tmp_path):
    """Interrupted JSON resumes once; exact composition reuse incurs no further calls."""
    source = tmp_path / "source.txt"
    source.write_text("source ethics", encoding="utf-8")
    full = json.dumps(make_draft(), ensure_ascii=False)
    fragments = [full[:70], full[70:]]
    calls = []
    class PartialDispatch:
        """Provide an interrupted composition followed by its exact suffix."""
        def call(self, role, prompt, system_prompt, **kwargs):
            """Record bounded dispatch and return the next fixture fragment."""
            calls.append(kwargs)
            return SimpleNamespace(content=fragments.pop(0), was_truncated=len(calls) == 1)
    runner = DynamicLiveCouncilRunner(dispatcher=PartialDispatch(), vector_store=FakeVector(),
        review_store=ReviewStore(tmp_path / "reviews.db"), example_registry=ExampleRegistry(tmp_path / "examples.db"),
        narada_sutras=[], shandilya_sutras=[], source_paths={"DOC-01": source}, run_id="continue")
    payload = {"mode": "compose", "inputs": []}
    assert runner._json_role("sutrakar_master", payload) == make_draft()
    assert runner._json_role("sutrakar_master", payload) == make_draft()
    assert len(calls) == 2
    assert all(call["allow_truncated"] for call in calls)

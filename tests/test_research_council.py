"""Offline contract checks; no providers, credentials, models, or network calls."""

import json
import sqlite3
from collections import Counter
from copy import deepcopy
from threading import Barrier, Lock

import pytest

from src.orchestration.research_council import (
    ResearchCouncil, TEXT_FIELDS, VOICES, authorize_schema_retry,
)


def entry(formula="उद्यमेन विवेकः", number=1):
    """Purpose: build a parent-enriched fixture. Parameters: formula, number.
    Returns: complete entry with immutable case metadata. Failures: none.
    """
    return {"new_sutra": formula, **{field: "Current evidence" for field in TEXT_FIELDS},
            "number": number, "chapter": "Research chapter", "exposition": ["Current evidence"],
            "references": ["S1"],
            "comparative_mr": [{"source_id": "S1", "explanation_mr": "Current comparison"}],
            "examples": [{"case_id": "case-a", "description_mr": "Verified case"}],
            "dos_mr": ["Act"], "donts_mr": ["Delay"],
            "case_pack": {"id": "immutable", "provenance": "parent supplied"},
            "usage": {"input_tokens": 123, "output_tokens": 45}}


def issue(field="new_sutra", quote="उद्यमेन विवेकः"):
    """Purpose: build grounded criticism. Parameters: field, quote.
    Returns: structured issue. Failures: none; callers may intentionally alter it.
    """
    return {"field": field, "quote": quote, "reason": "Needs author judgment",
            "severity": "major"}


class FakeCallbacks:
    """Observable synchronous callbacks with optional stage-specific overrides."""

    def __init__(self, overrides=None, parallel=False):
        """Purpose: configure fakes. Parameters: overrides, parallel barrier flag.
        Returns: None. Failures: none; barriers fail if rounds are serialized.
        """
        self.calls = []
        self.lock = Lock()
        self.overrides = overrides or {}
        self.barriers = {stage: Barrier(3 if stage == "peer_review" else 4, timeout=10)
                         for stage in ("position", "challenge", "reply", "peer_review")} if parallel else {}
        self.voices = {name: self.voice(name) for name in VOICES}

    def record(self, payload):
        """Purpose: retain exact dispatch. Parameters: payload. Returns: None.
        Failures: none for the fixture's JSON-compatible objects.
        """
        with self.lock:
            self.calls.append(deepcopy(payload))

    def voice(self, name):
        """Purpose: bind role identity. Parameters: name. Returns: callback.
        Failures: none; callback assertion failures are visible in checkpoints.
        """
        def answer(payload):
            """Purpose: answer one stage. Parameters: payload. Returns: dictionary.
            Failures: assertions/barrier errors for invalid orchestration.
            """
            self.record(payload)
            stage = payload["stage"]
            assert payload["speaker"] == name
            assert {"number", "brief", "sources", "discussion"} <= payload.keys()
            if stage in self.barriers:
                self.barriers[stage].wait()
            override = self.overrides.get((stage, name), self.overrides.get(stage))
            if override:
                return override(payload)
            if payload.get("scope") == "batch":
                return self.batch_answer(payload)
            if stage == "position":
                assert payload["discussion"] == {}
                return {"position": f"{name} cites available evidence", "usage": {"tokens": 4}}
            if stage == "challenge":
                assert set(payload["discussion"]["position"]) == set(VOICES)
                return {"challenges": {peer: f"{name} asks {peer}" for peer in VOICES if peer != name}}
            if stage == "reply":
                challenges = payload["discussion"]["challenge"]
                assert set(challenges) == set(VOICES)
                return {"answers": {peer: {"answer": challenges[peer]["challenges"][name]}
                                    for peer in VOICES if peer != name}}
            if stage == "proposal":
                return {"proposed_sutra": "उद्यमेन विवेकः", "rationale": "Brief public summary"}
            if stage == "peer_review":
                return {"verdict": "PASS", "issues": []}
            if stage.startswith("composition"):
                return entry(number=payload["number"])
            raise AssertionError(f"Unexpected voice stage {stage}")

        return answer

    def batch_answer(self, payload):
        """Purpose: answer every entry in a batch round. Parameters: payload.
        Returns: complete numbered coverage. Failures: assertions for lost briefs,
        sources, or challenges; no provider/model selection occurs in this fake.
        """
        numbers, name, stage = payload["entry_numbers"], payload["speaker"], payload["stage"]
        assert [b["number"] for b in payload["briefs"]] == numbers
        assert set(payload["sources_by_entry"]) == {str(n) for n in numbers}
        assert payload["sources"] == payload["sources_by_entry"]
        if stage == "position":
            return {"positions": {str(b["number"]): {"thesis": f"{name}: {b['reader_question']}",
                                  "evidence": "S1 evidence"} for b in payload["briefs"]}}
        if stage == "challenge":
            assert set(payload["discussion"]["position"]) == set(VOICES)
            return {"challenges": {peer: {str(n): f"{name} asks {peer} about entry {n}"
                                         for n in numbers} for peer in VOICES if peer != name}}
        if stage == "reply":
            challenges = payload["discussion"]["challenge"]
            return {"answers": {peer: {str(n): challenges[peer]["challenges"][name][str(n)]
                                      for n in numbers} for peer in VOICES if peer != name}}
        if stage == "proposal":
            return {"proposals": [{"number": n, "proposed_sutra": "उद्यमेन विवेकः",
                                   "derivation": f"Derivation for entry {n}",
                                   "selected_source_ids": ["S1"]} for n in numbers]}
        if stage == "peer_review":
            return {"reviews": [{"number": n, "verdict": "PASS", "issues": []} for n in numbers]}
        raise AssertionError(f"Unexpected batch stage {stage}")

    def validator(self, payload):
        """Purpose: inspect current draft only. Parameters: payload.
        Returns: review dictionary. Failures: assertions for leaked old proposals.
        """
        self.record(payload)
        assert payload["speaker"] == "validator"
        assert payload["discussion"] == {}
        assert "proposal" not in payload and "peer_review" not in payload
        assert payload["draft"]["case_pack"]["id"] == "immutable"
        override = self.overrides.get(payload["stage"], self.overrides.get("validator"))
        return override(payload) if override else {"verdict": "PASS", "issues": []}

    def assessor(self, draft, sources, prior, forbidden, used):
        """Purpose: mimic parent's acceptance policy. Parameters: five policy inputs.
        Returns: status/issues dictionary. Failures: assertions for altered inputs.
        """
        payload = {"stage": "assessor", "draft": draft, "sources": sources,
                   "prior": prior, "forbidden": forbidden, "used": sorted(used)}
        self.record(payload)
        assert isinstance(used, set)
        assert draft["case_pack"]["id"] == "immutable"
        override = self.overrides.get("assessor")
        return override(payload) if override else {"status": "PASS", "issues": []}

    def council(self, tmp_path, max_revisions=2, policy_corrections=None):
        """Purpose: create council fixture. Parameters: tmp_path, max_revisions, policy_corrections.
        Returns: ResearchCouncil. Failures: configuration or SQLite exceptions.
        """
        return ResearchCouncil(tmp_path / "research.db", self.voices, self.validator,
                               self.assessor, max_revisions, policy_corrections)


def inputs(number=1):
    """Purpose: supply source-pair-free inputs. Parameters: number.
    Returns: six run arguments. Failures: none.
    """
    return (number, {"reader_question": "How should we act?"},
            {"registered_knowledge": {"passages": [{"source_id": "S1", "text": "Evidence"}]}},
            ["Earlier formula"], ["Author original"], {"used-a", "used-b"})


def test_four_parallel_all_to_all_rounds_and_peer_coverage(tmp_path):
    """Purpose: prove all-to-all barriers. Parameters: tmp_path.
    Returns: None. Failures: assertions for missing peers or sequential calls.
    """
    fake = FakeCallbacks(parallel=True)
    result = fake.council(tmp_path).run(*inputs())
    for stage, key in (("challenge", "challenges"), ("reply", "answers")):
        assert set(result["discussion"][stage]) == set(VOICES)
        for name in VOICES:
            assert set(result["discussion"][stage][name][key]) == set(VOICES) - {name}
    assert set(result["peer_review"]) == set(VOICES[:-1])
    assert len(fake.calls) == 19
    assert result["draft"] == entry()
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW"
    assert result["revisions"] == 0


def test_validator_and_assessor_cannot_mutate_saved_draft_or_inputs(tmp_path):
    """Purpose: prove callback isolation. Parameters: tmp_path.
    Returns: None. Failures: assertions if a callback mutation escapes its copy.
    """
    def mutate(payload):
        """Purpose: attempt edits. Parameters: payload. Returns: valid review.
        Failures: none; mutation must be isolated by orchestration.
        """
        payload["draft"]["new_sutra"] = "Changed text"
        payload["draft"]["case_pack"].clear()
        payload["sources"].clear()
        return {"verdict": "PASS", "issues": []}

    def assess(payload):
        """Purpose: exercise assessor inputs. Parameters: payload. Returns: PASS.
        Failures: assertions if exclusion context is incomplete.
        """
        assert payload["prior"] == ["Earlier formula"]
        assert payload["forbidden"] == ["Author original"]
        assert payload["used"] == ["used-a", "used-b"]
        payload["draft"]["new_sutra"] = "Another edit"
        return {"status": "PASS", "issues": []}

    args = inputs()
    saved = deepcopy(args)
    result = FakeCallbacks({"validator": mutate, "assessor": assess}).council(tmp_path).run(*args)
    assert result["draft"] == entry()
    assert args == saved


def test_checkpoint_resume_uses_zero_callbacks_and_retains_usage(tmp_path):
    """Purpose: verify exact cache reuse. Parameters: tmp_path. Returns: None.
    Failures: assertions for extra callbacks, lost usage, or mutable cache data.
    """
    fake = FakeCallbacks()
    expected = fake.council(tmp_path).run(*inputs())
    fake.calls.clear()
    resumed = fake.council(tmp_path).run(*inputs())
    assert resumed == expected
    assert fake.calls == []
    resumed["draft"]["case_pack"].clear()
    assert fake.council(tmp_path).run(*inputs()) == expected
    with sqlite3.connect(tmp_path / "research.db") as db:
        raw = db.execute("SELECT response_json FROM research_attempts WHERE stage='composition'").fetchone()[0]
    assert json.loads(raw)["usage"] == entry()["usage"]


@pytest.mark.parametrize("changed", range(1, 6))
def test_stale_inputs_rejected_before_any_callback(tmp_path, changed):
    """Purpose: bind all inputs. Parameters: tmp_path, changed argument index.
    Returns: None. Failures: assertions if stale contexts reuse partial results.
    """
    fake = FakeCallbacks()
    fake.council(tmp_path).run(*inputs())
    fake.calls.clear()
    args = list(inputs())
    if isinstance(args[changed], dict):
        args[changed]["changed"] = True
    elif isinstance(args[changed], set):
        args[changed].add("changed")
    else:
        args[changed].append("changed")
    with pytest.raises(ValueError, match="Stale inputs"):
        fake.council(tmp_path).run(*args)
    assert fake.calls == []


@pytest.mark.parametrize("number", [1, 20, 21, 100, 101, 205])
def test_positive_numbering_has_no_arbitrary_upper_cap(tmp_path, number):
    """Purpose: check new numbering. Parameters: tmp_path, number.
    Returns: None. Failures: assertions for an inherited twenty/hundred-entry cap.
    """
    assert FakeCallbacks().council(tmp_path).run(*inputs(number))["status"] == "READY_FOR_AUTHOR_REVIEW"


@pytest.mark.parametrize("number", [0, -1, True, 1.5, "1"])
def test_invalid_number_never_dispatches(tmp_path, number):
    """Purpose: enforce numeric bounds. Parameters: tmp_path, number.
    Returns: None. Failures: assertions if invalid numbers invoke callbacks.
    """
    fake = FakeCallbacks()
    with pytest.raises(ValueError, match="positive integer"):
        fake.council(tmp_path).run(*inputs(number))
    assert fake.calls == []


@pytest.mark.parametrize("formula", ["one", "one two three four five", "a" * 32 + " b"])
def test_short_proposal_gate_precedes_expensive_stages_and_persists_failure(tmp_path, formula):
    """Purpose: stop invalid formulas early. Parameters: tmp_path, formula.
    Returns: None. Failures: assertions for expensive calls or reset retry budgets.
    """
    def proposal(payload):
        """Purpose: return bad shape. Parameters: payload. Returns: proposal.
        Failures: none; the council must reject this object.
        """
        return {"proposed_sutra": formula, "usage": {"tokens": 99}}

    fake = FakeCallbacks({"proposal": proposal})
    with pytest.raises(ValueError, match="Short-sutra gate"):
        fake.council(tmp_path).run(*inputs())
    assert Counter(p["stage"] for p in fake.calls) == {"position": 4, "challenge": 4, "reply": 4, "proposal": 2}
    fake.calls.clear()
    with pytest.raises(ValueError, match="Exhausted proposal"):
        fake.council(tmp_path).run(*inputs())
    assert fake.calls == []
    with sqlite3.connect(tmp_path / "research.db") as db:
        rows = db.execute("SELECT state,response_json,error FROM research_attempts WHERE stage='proposal'").fetchall()
    assert len(rows) == 2 and all(row[0] == "FAILED" for row in rows)
    assert all(json.loads(row[1])["usage"]["tokens"] == 99 and row[2] for row in rows)


@pytest.mark.parametrize("stage,key", [("challenge", "challenges"), ("reply", "answers")])
@pytest.mark.parametrize("defect", ["missing", "self", "alias", "empty"])
def test_exact_other_three_peer_keys_are_required(tmp_path, stage, key, defect):
    """Purpose: reject weak coverage. Parameters: tmp_path, stage, key, defect.
    Returns: None. Failures: assertions if approximate or extra peers pass.
    """
    def malformed(payload):
        """Purpose: return broken coverage. Parameters: payload. Returns: map.
        Failures: none; the council must reject it within two attempts.
        """
        peers = {peer: "Evidence" for peer in VOICES if peer != "narada"}
        if defect == "missing":
            peers.pop("researcher")
        elif defect == "self":
            peers["narada"] = "Self"
        elif defect == "alias":
            peers["to_researcher"] = peers.pop("researcher")
        else:
            peers["researcher"] = "  "
        return {key: peers}

    fake = FakeCallbacks({(stage, "narada"): malformed})
    with pytest.raises(ValueError, match=f"Exhausted {stage}/narada"):
        fake.council(tmp_path).run(*inputs())
    assert len([p for p in fake.calls if p["stage"] == stage and p["speaker"] == "narada"]) == 2


def test_failed_quality_is_bounded_and_never_reruns_council(tmp_path):
    """Purpose: prove maximum repair cycles. Parameters: tmp_path.
    Returns: None. Failures: assertions for excessive calls or false readiness.
    """
    def review(payload):
        """Purpose: report a valid unresolved defect. Parameters: payload.
        Returns: review. Failures: none.
        """
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue()]}

    def assess(payload):
        """Purpose: fail deterministic quality. Parameters: payload.
        Returns: failed assessment. Failures: none.
        """
        return {"status": "NEEDS_REVIEW", "issues": ["More source evidence needed"]}

    fake = FakeCallbacks({"validator": review, "assessor": assess})
    result = fake.council(tmp_path).run(*inputs())
    assert result["status"] == "NEEDS_REVIEW" and result["revisions"] == 2
    counts = Counter(p["stage"] for p in fake.calls)
    assert counts == {"position": 4, "challenge": 4, "reply": 4, "proposal": 1,
                      "peer_review": 3, "composition": 1, "composition_1": 1,
                      "composition_2": 1, "independent_review": 1,
                      "independent_review_1": 1, "independent_review_2": 1, "assessor": 3}
    fake.calls.clear()
    assert fake.council(tmp_path).run(*inputs()) == result
    assert fake.calls == []


@pytest.mark.parametrize("bad_review", [
    {"verdict": "APPROVED", "issues": []},
    {"verdict": "REVIEW_REQUIRED", "issues": ["Grammar wrong"]},
    {"verdict": "REVIEW_REQUIRED", "issues": [issue(quote="Abandoned proposal")]},
    {"verdict": "REVIEW_REQUIRED", "issues": [issue(field="not_a_field")]},
    {"verdict": "REVIEW_REQUIRED", "issues": [issue(field="translation_mr")]},
    {"verdict": "PASS", "issues": [issue()]},
    {"verdict": "REVIEW_REQUIRED", "issues": []},
    {"verdict": "PASS", "issues": [], "draft": entry("Changed text")},
])
def test_invalid_reviews_cannot_trigger_composition_repair(tmp_path, bad_review):
    """Purpose: fail ungrounded reviews closed. Parameters: tmp_path, bad_review.
    Returns: None. Failures: assertions if fabricated objections cause revisions.
    """
    def review(payload):
        """Purpose: emit invalid review. Parameters: payload. Returns: bad object.
        Failures: none; council must reject it as a schema failure.
        """
        return deepcopy(bad_review)

    fake = FakeCallbacks({"validator": review})
    with pytest.raises(ValueError, match="Invalid review"):
        fake.council(tmp_path).run(*inputs())
    assert len([p for p in fake.calls if p["stage"] == "independent_review"]) == 2
    assert [p["stage"] for p in fake.calls if p["stage"].startswith("composition")] == ["composition"]
    with sqlite3.connect(tmp_path / "research.db") as db:
        assert db.execute("SELECT COUNT(*) FROM research_stages WHERE stage='composition'").fetchone()[0] == 1


def test_corrected_review_quotes_current_draft_then_repairs_only_composition(tmp_path):
    """Purpose: separate review repair from draft repair. Parameters: tmp_path.
    Returns: None. Failures: assertions for stale proposal feedback or lost drafts.
    """
    def review(payload):
        """Purpose: fix invalid quotation on second attempt. Parameters: payload.
        Returns: current-draft issue. Failures: none.
        """
        quote = "Verified case" if "repair_feedback" in payload else "Old proposal"
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue("examples[0].description_mr", quote)]}

    def repair(payload):
        """Purpose: repair one draft. Parameters: payload. Returns: new entry.
        Failures: assertions if historical proposal complaints enter repair.
        """
        assert "proposal" not in payload and "peer_review" not in payload
        assert payload["review"]["issues"][0]["quote"] == "Verified case"
        return entry("सत्यं व्यवसायस्य मूलम्")

    def retain_concern(payload):
        """Purpose: retain a current defect on reconsideration. Parameters: payload.
        Returns: grounded review. Failures: none; a composition repair is still needed.
        """
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue("examples[0].description_mr", "Verified case")]}

    fake = FakeCallbacks({"independent_review": review, "composition_1": repair,
                          "independent_review_reconsideration": retain_concern})
    result = fake.council(tmp_path).run(*inputs())
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW" and result["revisions"] == 1
    assert result["draft"]["new_sutra"] == "सत्यं व्यवसायस्य मूलम्"
    with sqlite3.connect(tmp_path / "research.db") as db:
        assert db.execute("SELECT COUNT(*) FROM research_stages WHERE stage LIKE 'composition%'").fetchone()[0] == 2


def test_partial_failure_resumes_ready_siblings_without_extra_calls(tmp_path):
    """Purpose: recover completed peers after interruption. Parameters: tmp_path.
    Returns: None. Failures: assertions if successful parallel output is lost.
    """
    fake = FakeCallbacks()
    council = fake.council(tmp_path)
    original = council._parallel

    def interrupt(base, stage, speakers, **context):
        """Purpose: simulate stop at a round boundary. Parameters: round arguments.
        Returns: normal results before stop. Failures: RuntimeError at challenge.
        """
        if stage == "challenge":
            raise RuntimeError("simulated process stop")
        return original(base, stage, speakers, **context)

    council._parallel = interrupt
    with pytest.raises(RuntimeError, match="process stop"):
        council.run(*inputs())
    assert len(fake.calls) == 4
    fake.calls.clear()
    assert fake.council(tmp_path).run(*inputs())["status"] == "READY_FOR_AUTHOR_REVIEW"
    assert len(fake.calls) == 15
    assert not any(p["stage"] == "position" for p in fake.calls)


def test_schema_retry_and_callback_exception_are_both_persisted(tmp_path):
    """Purpose: bound outages and preserve siblings. Parameters: tmp_path.
    Returns: None. Failures: assertions for unrecorded errors or paid retry loops.
    """
    def fail(payload):
        """Purpose: simulate parent parser/provider failure. Parameters: payload.
        Returns: nothing. Failures: ValueError for malformed provider JSON.
        """
        raise ValueError("Parent JSON parse failed")

    fake = FakeCallbacks({("position", "narada"): fail})
    with pytest.raises(ValueError, match="Parent JSON parse failed"):
        fake.council(tmp_path).run(*inputs())
    with sqlite3.connect(tmp_path / "research.db") as db:
        assert db.execute("SELECT COUNT(*) FROM research_stages WHERE stage='position'").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM research_attempts WHERE state='FAILED'").fetchone()[0] == 2
    fake.calls.clear()
    with pytest.raises(ValueError, match="Exhausted"):
        fake.council(tmp_path).run(*inputs())
    assert fake.calls == []


@pytest.mark.parametrize("budget", [-1, 3, True, 1.5])
def test_repair_budget_cannot_exceed_two(tmp_path, budget):
    """Purpose: reject unbounded configuration. Parameters: tmp_path, budget.
    Returns: None. Failures: assertions for accepted invalid repair budgets.
    """
    with pytest.raises(ValueError, match="max_revisions"):
        FakeCallbacks().council(tmp_path, budget)


def test_validator_cannot_be_a_council_voice(tmp_path):
    """Purpose: enforce distinct validator wiring. Parameters: tmp_path.
    Returns: None. Failures: assertions if a discussion callback is the validator.
    """
    fake = FakeCallbacks()
    with pytest.raises(ValueError, match="independent"):
        ResearchCouncil(tmp_path / "bad.db", fake.voices, fake.voices["narada"], fake.assessor)


@pytest.mark.parametrize("field,bad_value", [
    ("grammar_mr", None), ("translation_mr", ""), ("exposition", "Not a list"),
    ("exposition", [None]), ("comparative_mr", "Not a list"),
    ("application_mr", None), ("action_mr", ""), ("summary_mr", {}),
    ("number", 2), ("chapter", False), ("references", {}),
])
def test_new_composition_schema_has_two_attempts_before_any_review(tmp_path, field, bad_value):
    """Purpose: enforce new entry shape. Parameters: tmp_path, field, bad_value.
    Returns: None. Failures: assertions for legacy schema or premature review.
    """
    def compose(payload):
        """Purpose: emit one malformed new entry. Parameters: payload.
        Returns: fixture with invalid field. Failures: none.
        """
        draft = entry()
        draft[field] = bad_value
        return draft

    fake = FakeCallbacks({"composition": compose})
    with pytest.raises(ValueError, match="Exhausted composition"):
        fake.council(tmp_path).run(*inputs())
    assert len([p for p in fake.calls if p["stage"] == "composition"]) == 2
    assert not any(p["stage"].startswith("independent_review") for p in fake.calls)
    assert not any(p["stage"] == "assessor" for p in fake.calls)


@pytest.mark.parametrize("budget", [0, 1, 2])
def test_assessment_failure_overrides_validator_pass_with_bounded_repairs(tmp_path, budget):
    """Purpose: require both gates to pass. Parameters: tmp_path, budget.
    Returns: None. Failures: assertions for false readiness or excess repairs.
    """
    def assess(payload):
        """Purpose: signal missing canonical mapping. Parameters: payload.
        Returns: failed assessment. Failures: none.
        """
        return {"status": "NEEDS_REVISION", "issues": ["Missing comparison for reference S1"]}

    fake = FakeCallbacks({"assessor": assess})
    result = fake.council(tmp_path, budget).run(*inputs())
    assert result["review"]["verdict"] == "PASS"
    assert result["status"] == "NEEDS_REVIEW" and result["revisions"] == budget
    assert len([p for p in fake.calls if p["stage"].startswith("composition")]) == budget + 1


@pytest.mark.parametrize("defect", [None, "no_reference", "missing_comparison", "unknown_reference"])
def test_real_acceptance_checks_selected_reference_and_comparative_mapping(tmp_path, defect):
    """Purpose: integrate new schema with offline policy. Parameters: tmp_path, defect.
    Returns: None. Failures: assertions if absent references/mappings become ready.
    """
    from src.orchestration.research_acceptance import assess_research_entry

    packet = {"references": [{"id": "S1", "title": "Evidence", "author": "Author",
                              "locator": "Section 1", "original_text": "Source passage",
                              "meaning_mr": "स्रोतार्थ", "url": "https://example.org/source",
                              "tradition": "Management"}],
              "examples": [{"case_id": f"new-{kind}", "kind": kind,
                            "entity": f"Case {kind}", "text_mr": "सत्य प्रसंग",
                            "url": f"https://example.org/{kind}", "source_title": "Case source"}
                           for kind in ("positive", "caution")]}

    def compose(payload):
        """Purpose: return complete parent-enriched entry. Parameters: payload.
        Returns: new schema with exact canonical cases. Failures: none.
        """
        draft = entry()
        draft.update(exposition=["उद्योग " * 500], examples=deepcopy(packet["examples"]),
                     dos_mr=["करा"] * 3, donts_mr=["टाळा"] * 3)
        if defect == "no_reference":
            draft["references"] = []
        elif defect == "missing_comparison":
            draft["comparative_mr"] = []
        elif defect == "unknown_reference":
            draft["references"] = ["unregistered"]
        return draft

    fake = FakeCallbacks({"composition": compose})
    council = ResearchCouncil(tmp_path / "research.db", fake.voices, fake.validator,
                               assess_research_entry, max_revisions=0)
    args = list(inputs())
    args[2] = packet
    result = council.run(*args)
    assert result["draft"]["examples"] == packet["examples"]
    assert result["status"] == ("NEEDS_REVIEW" if defect else "READY_FOR_AUTHOR_REVIEW")
    assert (result["assessment"]["status"] == "PASS") == (defect is None)


def test_changed_revision_budget_rejects_stale_run(tmp_path):
    """Purpose: freeze retry policy across resumes. Parameters: tmp_path.
    Returns: None. Failures: assertions for resetting the allowed revision budget.
    """
    fake = FakeCallbacks()
    fake.council(tmp_path, 0).run(*inputs())
    fake.calls.clear()
    with pytest.raises(ValueError, match="Stale inputs"):
        fake.council(tmp_path, 2).run(*inputs())
    assert fake.calls == []


def test_uncertain_inflight_callback_is_not_automatically_replayed(tmp_path):
    """Purpose: protect uncertain external call outcomes. Parameters: tmp_path.
    Returns: None. Failures: assertions for duplicate dispatch after a hard crash.
    """
    fake = FakeCallbacks()
    fake.council(tmp_path).run(*inputs())
    with sqlite3.connect(tmp_path / "research.db") as db:
        db.execute("DELETE FROM research_stages WHERE stage='independent_review'")
        db.execute("UPDATE research_attempts SET state='RUNNING',response_json=NULL "
                   "WHERE stage='independent_review'")
    fake.calls.clear()
    with pytest.raises(ValueError, match="Unresolved in-flight"):
        fake.council(tmp_path).run(*inputs())
    assert fake.calls == []


def batch_inputs(numbers=(101, 102, 103, 104, 105)):
    """Purpose: build distinct related briefs. Parameters: numbers.
    Returns: batch method arguments. Failures: none for positive fixture numbers.
    """
    briefs = [{"number": n, "reader_question": f"Theme {n}", "chapter": "Shared theme"}
              for n in numbers]
    sources = {str(n): {"references": [{"id": "S1", "original_text": f"Evidence {n}"}]}
               for n in numbers}
    return ("theme-batch", briefs, sources, ["Earlier formula"], ["Author original"])


def compose_batch(council, args, batch):
    """Purpose: mirror parent per-entry dispatch. Parameters: council, args, batch.
    Returns: result list. Failures: council errors propagate; no providers used.
    """
    _, briefs, sources, initial_prior, forbidden = args
    prior = list(initial_prior)
    results = []
    for brief in briefs:
        result = council.compose_entry(brief["number"], brief, sources[str(brief["number"])],
                                       prior, forbidden, set(), batch["discussion"],
                                       batch["proposal"], batch["peer_review"])
        results.append(result)
        prior.append(result["draft"]["new_sutra"])
    return results


def test_batch_full_coverage_parallel_roles_and_exact_claude_call_count(tmp_path):
    """Purpose: prove cost reduction without lost roles. Parameters: tmp_path.
    Returns: None. Failures: assertions for omitted entries/peers or extra calls.
    """
    fake = FakeCallbacks(parallel=True)
    original_voices = dict(fake.voices)
    council = fake.council(tmp_path, max_revisions=1)
    args = batch_inputs()
    batch = council.run_batch_discussion(*args)
    assert len(fake.calls) == 16
    assert Counter(p["speaker"] for p in fake.calls) == {
        "narada": 4, "shandilya": 4, "researcher": 4, "sutrakar": 4}
    numbers = {str(b["number"]) for b in args[1]}
    for role in VOICES:
        assert set(batch["discussion"]["position"][role]["positions"]) == numbers
        for stage, field in (("challenge", "challenges"), ("reply", "answers")):
            peers = batch["discussion"][stage][role][field]
            assert set(peers) == set(VOICES) - {role}
            assert all(set(records) == numbers for records in peers.values())
    results = compose_batch(council, args, batch)
    assert all(r["status"] == "READY_FOR_AUTHOR_REVIEW" for r in results)
    assert len([p for p in fake.calls if p.get("speaker") in {"researcher", "sutrakar"}]) == 13
    assert len([p for p in fake.calls if p.get("speaker") == "validator"]) == 5
    assert all(council.voices[role] is original_voices[role] for role in VOICES)
    for result, brief in zip(results, args[1]):
        assert result["proposal"]["number"] == brief["number"]
        assert all(r["number"] == brief["number"] for r in result["peer_review"].values())


def test_batch_and_compositions_resume_without_any_additional_callback(tmp_path):
    """Purpose: verify shared checkpoint replay. Parameters: tmp_path.
    Returns: None. Failures: assertions for extra model calls or changed results.
    """
    fake = FakeCallbacks()
    args = batch_inputs()
    council = fake.council(tmp_path)
    batch = council.run_batch_discussion(*args)
    expected = compose_batch(council, args, batch)
    fake.calls.clear()
    resumed = fake.council(tmp_path)
    cached = resumed.run_batch_discussion(*args)
    assert cached == batch
    assert compose_batch(resumed, args, cached) == expected
    assert fake.calls == []


def test_batch_databases_are_separate_from_entries_and_each_other(tmp_path):
    """Purpose: prevent batch/entry key collisions. Parameters: tmp_path.
    Returns: None. Failures: assertions for shared DB identities or missing rows.
    """
    fake = FakeCallbacks()
    council = fake.council(tmp_path)
    args = list(batch_inputs((1,)))
    args[0] = "../first/batch"
    first = council.run_batch_discussion(*args)
    args[0] = "second"
    second = council.run_batch_discussion(*args)
    assert first["checkpoint_path"] != second["checkpoint_path"]
    from pathlib import Path
    assert Path(first["checkpoint_path"]).parent == tmp_path
    with sqlite3.connect(tmp_path / "research.db") as db:
        assert db.execute("SELECT COUNT(*) FROM research_stages").fetchone()[0] == 0
    for batch in (first, second):
        with sqlite3.connect(batch["checkpoint_path"]) as db:
            assert db.execute("SELECT COUNT(*) FROM research_stages").fetchone()[0] == 16
            assert db.execute("SELECT DISTINCT number FROM research_stages").fetchall() == [(0,)]
    assert council.run(*inputs(1))["status"] == "READY_FOR_AUTHOR_REVIEW"


@pytest.mark.parametrize("changed", [1, 2, 3, 4])
def test_batch_stale_inputs_rejected_before_callbacks(tmp_path, changed):
    """Purpose: freeze all batch evidence. Parameters: tmp_path, changed index.
    Returns: None. Failures: assertions for reuse after changed batch inputs.
    """
    fake = FakeCallbacks()
    args = list(batch_inputs())
    fake.council(tmp_path).run_batch_discussion(*args)
    if changed == 1:
        args[1][0]["reader_question"] = "Changed theme"
    elif changed == 2:
        args[2]["101"]["references"] = []
    else:
        args[changed].append("New exclusion")
    fake.calls.clear()
    with pytest.raises(ValueError, match="Stale inputs"):
        fake.council(tmp_path).run_batch_discussion(*args)
    assert fake.calls == []


@pytest.mark.parametrize("stage", ["position", "challenge", "reply"])
@pytest.mark.parametrize("defect", ["missing_entry", "empty_entry", "extra_entry"])
def test_batch_every_voice_must_cover_every_entry_in_all_rounds(tmp_path, stage, defect):
    """Purpose: reject aggregate handwaving. Parameters: tmp_path, stage, defect.
    Returns: None. Failures: assertions for missing substantive per-entry work.
    """
    fake = FakeCallbacks()

    def malformed(payload):
        """Purpose: damage one role's coverage. Parameters: payload. Returns: map.
        Failures: none; stage validation must reject within two attempts.
        """
        answer = fake.batch_answer(payload)
        field = {"position": "positions", "challenge": "challenges", "reply": "answers"}[stage]
        mapping = answer[field] if stage == "position" else answer[field]["shandilya"]
        if defect == "missing_entry":
            mapping.pop("103")
        elif defect == "empty_entry":
            mapping["103"] = {}
        else:
            mapping["999"] = "Unexpected entry"
        return answer

    fake.overrides[(stage, "narada")] = malformed
    with pytest.raises(ValueError, match=f"Exhausted {stage}/narada"):
        fake.council(tmp_path).run_batch_discussion(*batch_inputs())
    assert len([p for p in fake.calls if p["stage"] == stage and p["speaker"] == "narada"]) == 2
    assert not any(p["stage"] == "proposal" for p in fake.calls)


@pytest.mark.parametrize("defect", ["missing", "duplicate", "extra", "bool_number", "long", "derivation", "source_ids"])
def test_batch_proposals_exact_numbers_and_short_gate_before_peer_review(tmp_path, defect):
    """Purpose: gate the entire proposal set. Parameters: tmp_path, defect.
    Returns: None. Failures: assertions for partial/overlong batch proposals.
    """
    fake = FakeCallbacks()

    def malformed(payload):
        """Purpose: emit invalid batch proposal. Parameters: payload. Returns: map.
        Failures: none; council must stop before any paid peer review.
        """
        answer = fake.batch_answer(payload)
        records = answer["proposals"]
        if defect == "missing":
            records.pop()
        elif defect == "duplicate":
            records[-1]["number"] = records[0]["number"]
        elif defect == "extra":
            records.append({**records[0], "number": 999})
        elif defect == "bool_number":
            records[0]["number"] = True
        elif defect == "long":
            records[0]["proposed_sutra"] = "one two three four five"
        elif defect == "derivation":
            records[0]["derivation"] = ""
        else:
            records[0]["selected_source_ids"] = "S1"
        return answer

    fake.overrides["proposal"] = malformed
    with pytest.raises(ValueError, match="Exhausted proposal"):
        fake.council(tmp_path).run_batch_discussion(*batch_inputs())
    assert len([p for p in fake.calls if p["stage"] == "proposal"]) == 2
    assert not any(p["stage"] == "peer_review" for p in fake.calls)


def test_batch_reviews_need_exact_numbers_and_quotes_for_their_own_proposal(tmp_path):
    """Purpose: prevent review cross-contamination. Parameters: tmp_path.
    Returns: None. Failures: assertions if one entry cites another's derivation.
    """
    fake = FakeCallbacks()

    def review(payload):
        """Purpose: quote a different entry's derivation. Parameters: payload.
        Returns: invalid reviews array. Failures: none.
        """
        answer = fake.batch_answer(payload)
        answer["reviews"][0].update(verdict="REVIEW_REQUIRED", issues=[
            issue("derivation", "Derivation for entry 102")])
        return answer

    fake.overrides[("peer_review", "narada")] = review
    with pytest.raises(ValueError, match="quote absent"):
        fake.council(tmp_path).run_batch_discussion(*batch_inputs())


@pytest.mark.parametrize("change", ["brief", "sources", "proposal", "review", "prior", "forbidden"])
def test_compose_entry_rejects_mismatched_batch_context_before_calls(tmp_path, change):
    """Purpose: bind selected entry to batch evidence. Parameters: tmp_path, change.
    Returns: None. Failures: assertions if mismatched inputs trigger composition.
    """
    fake = FakeCallbacks()
    council = fake.council(tmp_path)
    args = batch_inputs()
    batch = council.run_batch_discussion(*args)
    brief, sources = deepcopy(args[1][0]), deepcopy(args[2]["101"])
    prior, forbidden = list(args[3]), list(args[4])
    proposal = deepcopy(batch["proposal"]["proposals"][0])
    peer = {role: deepcopy(value["reviews"][0]) for role, value in batch["peer_review"].items()}
    if change == "brief":
        brief["reader_question"] = "Changed"
    elif change == "sources":
        sources.clear()
    elif change == "proposal":
        proposal["number"] = 102
    elif change == "review":
        peer["narada"]["number"] = 102
    elif change == "prior":
        prior.clear()
    else:
        forbidden.append("New exclusion")
    fake.calls.clear()
    with pytest.raises(ValueError):
        council.compose_entry(101, brief, sources, prior, forbidden, set(),
                              batch["discussion"], proposal, peer)
    assert fake.calls == []


def test_compose_accepts_selected_records_and_obeys_one_repair_budget(tmp_path):
    """Purpose: honor parent's lowered repair cap. Parameters: tmp_path.
    Returns: None. Failures: assertions for extra Claude calls or lost isolation.
    """
    def review(payload):
        """Purpose: keep one defect unresolved. Parameters: payload.
        Returns: current-draft review. Failures: none.
        """
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue()]}

    fake = FakeCallbacks({"validator": review})
    council = fake.council(tmp_path, 1)
    args = batch_inputs((101,))
    batch = council.run_batch_discussion(*args)
    fake.calls.clear()
    result = council.compose_entry(101, args[1][0], args[2]["101"], args[3], args[4], set(),
                                   batch["discussion"], batch["proposal"]["proposals"][0],
                                   {role: value["reviews"][0] for role, value in batch["peer_review"].items()})
    assert result["status"] == "NEEDS_REVIEW" and result["revisions"] == 1
    assert Counter(p["stage"] for p in fake.calls) == {
        "composition": 1, "composition_1": 1, "assessor": 2,
        "independent_review": 1, "independent_review_1": 1,
        "independent_review_reconsideration": 1}


def test_hard_callback_failure_is_terminal_persisted_and_never_retried(tmp_path):
    """Purpose: stop provider outages without schema retries. Parameters: tmp_path.
    Returns: None. Failures: assertions for duplicate external calls after failure.
    """
    def hard_failure(payload):
        """Purpose: simulate provider auth/quota/timeout error. Parameters: payload.
        Returns: never. Failures: ConnectionError, deliberately not a schema error.
        """
        raise ConnectionError("Provider unavailable")

    fake = FakeCallbacks({("position", "narada"): hard_failure})
    with pytest.raises(ConnectionError, match="Provider unavailable"):
        fake.council(tmp_path).run_batch_discussion(*batch_inputs())
    assert len([p for p in fake.calls if p["speaker"] == "narada"]) == 1
    fake.calls.clear()
    with pytest.raises(ValueError, match="Terminal callback failure"):
        fake.council(tmp_path).run_batch_discussion(*batch_inputs())
    assert fake.calls == []
    with sqlite3.connect(next(tmp_path.glob("*.batch-*.sqlite3"))) as db:
        assert db.execute("SELECT state FROM research_attempts WHERE speaker='narada'").fetchall() == [("HARD_FAILED",)]


def test_batch_validator_gets_selected_peer_concerns_without_old_quotes_or_edit_power(tmp_path):
    """Purpose: carry selected concerns through independent review at no extra cost.
    Parameters: tmp_path. Returns: None. Failures: assertions for leaked old quotes,
    cross-entry concerns, mutable drafts, forced rejection, or additional calls.
    """
    fake = FakeCallbacks()

    def peer(payload):
        """Purpose: flag each proposal separately. Parameters: payload.
        Returns: numbered reviews. Failures: none; quotes match current proposals.
        """
        return {"reviews": [{"number": n, "verdict": "REVIEW_REQUIRED", "issues": [
            {**issue("proposed_sutra"), "reason": f"Clarify the principle for entry {n}"}]
            } for n in payload["entry_numbers"]]}

    def compose(payload):
        """Purpose: resolve the proposal concern with fresh wording. Parameters: payload.
        Returns: complete current entry. Failures: none.
        """
        return entry("सत्यं व्यवसायस्य मूलम्", payload["number"])

    def review(payload):
        """Purpose: inspect concerns then attempt mutation. Parameters: payload.
        Returns: PASS for resolved concerns. Failures: assertions on context leaks.
        """
        assert payload["peer_concerns"] == [{
            "role": "narada", "reason": f"Clarify the principle for entry {payload['number']}",
            "severity": "major"}]
        assert "उद्यमेन विवेकः" not in json.dumps(payload, ensure_ascii=False)
        assert "CURRENT draft" in payload["review_instruction"]
        assert "Resolved concerns may PASS" in payload["review_instruction"]
        payload["draft"]["new_sutra"] = "Unauthorized edit"
        payload["peer_concerns"][0]["reason"] = "Unauthorized concern edit"
        return {"verdict": "PASS", "issues": []}

    fake.overrides.update({("peer_review", "narada"): peer, "composition": compose,
                           "validator": review})
    args = batch_inputs((101, 102))
    council = fake.council(tmp_path)
    batch = council.run_batch_discussion(*args)
    results = compose_batch(council, args, batch)
    assert len(fake.calls) == 22  # 16 shared + 2 compositions/assessments/reviews.
    assert all(r["status"] == "READY_FOR_AUTHOR_REVIEW" and r["revisions"] == 0 for r in results)
    assert all(r["draft"]["new_sutra"] == "सत्यं व्यवसायस्य मूलम्" for r in results)
    for result in results:
        assert result["peer_review"]["narada"]["verdict"] == "REVIEW_REQUIRED"
        assert "Unauthorized" not in json.dumps(result)
    fake.calls.clear()
    resumed = fake.council(tmp_path)
    assert compose_batch(resumed, args, resumed.run_batch_discussion(*args)) == results
    assert fake.calls == []


def test_peer_concerns_remain_visible_on_existing_revision_review(tmp_path):
    """Purpose: preserve concerns across bounded repairs. Parameters: tmp_path.
    Returns: None. Failures: assertions for lost context or additional review calls.
    """
    def peer(payload):
        """Purpose: flag the proposal. Parameters: payload. Returns: grounded review.
        Failures: none.
        """
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue("proposed_sutra")]}

    def review(payload):
        """Purpose: fail current grammar once. Parameters: payload. Returns: verdict.
        Failures: assertions for absent or incorrectly expanded concern fields.
        """
        assert payload["peer_concerns"] == [{"role": "narada", "reason": "Needs author judgment",
                                            "severity": "major"}]
        if payload["stage"] != "independent_review_1":
            return {"verdict": "REVIEW_REQUIRED", "issues": [issue("grammar_mr", "Current evidence")]}
        return {"verdict": "PASS", "issues": []}

    fake = FakeCallbacks({("peer_review", "narada"): peer, "validator": review})
    result = fake.council(tmp_path, 1).run(*inputs())
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW" and result["revisions"] == 1
    assert len(fake.calls) == 23


@pytest.mark.parametrize("defect", ["obsolete_quote", "edited_draft"])
def test_peer_concerns_do_not_relax_literal_quote_or_no_edit_checks(tmp_path, defect):
    """Purpose: retain independent reviewer constraints. Parameters: tmp_path, defect.
    Returns: None. Failures: assertions if concerns allow stale quotes or edits.
    """
    def peer(payload):
        """Purpose: create a historical concern. Parameters: payload. Returns: review.
        Failures: none; the proposal quotation is valid only at peer-review time.
        """
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue("proposed_sutra")]}

    def compose(payload):
        """Purpose: replace old wording. Parameters: payload. Returns: complete entry.
        Failures: none.
        """
        return entry("सत्यं व्यवसायस्य मूलम्")

    def review(payload):
        """Purpose: attempt invalid review despite concerns. Parameters: payload.
        Returns: stale quotation or an edit. Failures: none; council must reject.
        """
        assert payload["peer_concerns"]
        if defect == "edited_draft":
            return {"verdict": "PASS", "issues": [], "edited_draft": entry()}
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue()]}

    fake = FakeCallbacks({("peer_review", "narada"): peer, "composition": compose, "validator": review})
    with pytest.raises(ValueError, match="Invalid review"):
        fake.council(tmp_path).run(*inputs())
    assert len([p for p in fake.calls if p["stage"] == "independent_review"]) == 2
    assert [p["stage"] for p in fake.calls if p["stage"].startswith("composition")] == ["composition"]


def test_authorized_schema_retry_resumes_batch_without_replaying_cached_claude(tmp_path):
    """Purpose: recover only an exhausted Shandilya reply. Parameters: tmp_path.
    Returns: None. Failures: assertions for altered history, duplicate paid work,
    missing audit reason/time or a repeatable authorization.
    """
    fake = FakeCallbacks()

    def incomplete(payload):
        """Purpose: simulate the paid batch's missing entry coverage. Parameters: payload.
        Returns: malformed reply. Failures: none; normal schema budget exhausts.
        """
        answer = fake.batch_answer(payload)
        for records in answer["answers"].values():
            records.pop("5")
            records.pop("6")
        return answer

    fake.overrides[("reply", "shandilya")] = incomplete
    council = fake.council(tmp_path, 1)
    args = batch_inputs((2, 3, 4, 5, 6))
    with pytest.raises(ValueError, match="Exhausted reply/shandilya"):
        council.run_batch_discussion(*args)
    path = next(tmp_path.glob("*.batch-*.sqlite3"))
    with sqlite3.connect(path) as db:
        failed_before = db.execute("SELECT * FROM research_attempts WHERE stage='reply' AND speaker='shandilya'").fetchall()
        stages_before = db.execute("SELECT * FROM research_stages").fetchall()
        runs_before = db.execute("SELECT * FROM research_runs").fetchall()
    assert len(stages_before) == 11
    record = authorize_schema_retry(path, 0, "reply", "shandilya", "Explicit all-peer/all-entry skeleton added")
    assert record["max_attempts"] == 3 and record["authorized_at"]
    assert record["reason"] == "Explicit all-peer/all-entry skeleton added"
    with pytest.raises(ValueError, match="already authorized"):
        authorize_schema_retry(path, 0, "reply", "shandilya", "Cannot authorize twice")
    del fake.overrides[("reply", "shandilya")]
    fake.calls.clear()
    batch = fake.council(tmp_path, 1).run_batch_discussion(*args)
    assert Counter((p["stage"], p["speaker"]) for p in fake.calls) == {
        ("reply", "shandilya"): 1, ("proposal", "sutrakar"): 1,
        ("peer_review", "narada"): 1, ("peer_review", "shandilya"): 1,
        ("peer_review", "researcher"): 1}
    # The only new Claude calls are previously unexecuted proposal/peer stages.
    assert not any(p["speaker"] in {"sutrakar", "researcher"} and
                   p["stage"] in {"position", "challenge", "reply"} for p in fake.calls)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM research_attempts WHERE stage='reply' AND speaker='shandilya' AND attempt<=2").fetchall() == failed_before
        assert db.execute("SELECT * FROM research_runs").fetchall() == runs_before
        after = db.execute("SELECT * FROM research_stages").fetchall()
        assert all(row in after for row in stages_before)
        assert db.execute("SELECT attempt,state FROM research_attempts WHERE stage='reply' AND speaker='shandilya' ORDER BY attempt").fetchall() == [(1, "FAILED"), (2, "FAILED"), (3, "COMPLETE")]
    fake.calls.clear()
    assert fake.council(tmp_path, 1).run_batch_discussion(*args) == batch
    assert fake.calls == []


def test_authorized_schema_retry_is_exactly_one_extra_even_if_it_fails(tmp_path):
    """Purpose: forbid a fourth attempt or sibling budget expansion. Parameters: tmp_path.
    Returns: None. Failures: assertions for repeatable or broadly applied retries.
    """
    calls = []

    def invalid(payload):
        """Purpose: record one invalid schema response. Parameters: payload.
        Returns: empty object. Failures: none; council must enforce the budget.
        """
        calls.append(payload["speaker"])
        return {}

    council = FakeCallbacks().council(tmp_path)
    base = {"number": 0, "stage": "position", "brief": {}, "sources": {}, "discussion": {}}
    for role in ("shandilya", "narada"):
        with pytest.raises(ValueError, match="Exhausted"):
            council._stage({**base, "speaker": role}, invalid)
    council.authorize_schema_retry(0, "position", "shandilya", "One narrow schema correction")
    calls.clear()
    for role in ("narada", "shandilya", "shandilya"):
        with pytest.raises(ValueError, match="Exhausted"):
            council._stage({**base, "speaker": role}, invalid)
    assert calls == ["shandilya"]
    with pytest.raises(ValueError, match="already authorized"):
        council.authorize_schema_retry(0, "position", "shandilya", "Fourth attempt forbidden")


@pytest.mark.parametrize("states", [[], ["FAILED"], ["FAILED", "RUNNING"],
                                    ["FAILED", "HARD_FAILED"], ["HARD_FAILED", "FAILED"],
                                    ["FAILED", "COMPLETE"], ["FAILED", "FAILED", "FAILED"]])
def test_schema_retry_rejects_ineligible_attempt_histories(tmp_path, states):
    """Purpose: reject incomplete/hard/in-flight histories. Parameters: tmp_path, states.
    Returns: None. Failures: assertions if authorization bypasses terminal safety.
    """
    council = FakeCallbacks().council(tmp_path)
    with sqlite3.connect(council.path) as db:
        for attempt, state in enumerate(states, 1):
            db.execute("INSERT INTO research_attempts VALUES (?,?,?,?,?,?,?,?)",
                       (0, "reply", "shandilya", attempt, "a" * 64, state, "{}", "ValueError: Missing peers"))
    with pytest.raises(ValueError, match="exactly two matching FAILED"):
        authorize_schema_retry(council.path, 0, "reply", "shandilya", "Recovery requested")
    with sqlite3.connect(council.path) as db:
        assert db.execute("SELECT COUNT(*) FROM research_schema_retry_authorizations").fetchone()[0] == 0
        assert db.execute("SELECT state FROM research_attempts ORDER BY attempt").fetchall() == [(state,) for state in states]


def test_schema_retry_requires_reason_and_matching_hash_and_preserves_stale_checks(tmp_path):
    """Purpose: bind authorization to exact evidence. Parameters: tmp_path.
    Returns: None. Failures: assertions for empty reasons, hash drift or new files.
    """
    council = FakeCallbacks().council(tmp_path)
    with pytest.raises(ValueError, match="nonempty retry reason"):
        authorize_schema_retry(council.path, 0, "reply", "shandilya", " ")
    with pytest.raises(ValueError, match="existing checkpoint"):
        authorize_schema_retry(tmp_path / "absent.db", 0, "reply", "shandilya", "Reason")
    assert not (tmp_path / "absent.db").exists()
    with sqlite3.connect(council.path) as db:
        for attempt, digest in ((1, "a" * 64), (2, "b" * 64)):
            db.execute("INSERT INTO research_attempts VALUES (?,?,?,?,?,?,?,?)",
                       (0, "reply", "shandilya", attempt, digest, "FAILED", "{}", "ValueError: Missing peers"))
    with pytest.raises(ValueError, match="exactly two matching FAILED"):
        authorize_schema_retry(council.path, 0, "reply", "shandilya", "Reason")
    with sqlite3.connect(council.path) as db:
        db.execute("UPDATE research_attempts SET request_hash=?", ("a" * 64,))
    authorize_schema_retry(council.path, 0, "reply", "shandilya", "Reason")
    fake = FakeCallbacks()
    with pytest.raises(ValueError, match="Stale failed request"):
        council._stage({"number": 0, "stage": "reply", "speaker": "shandilya",
                        "brief": {}, "sources": {}, "discussion": {}}, fake.voices["shandilya"])
    assert fake.calls == []


def test_reconsideration_can_resolve_review_without_claude_repair_or_draft_edits(tmp_path):
    """Purpose: allow a warranted cheaper review correction. Parameters: tmp_path.
    Returns: None. Failures: assertions for extra composition, edit leakage or lost history.
    """
    def original(payload):
        """Purpose: flag an over-specific expression concern. Parameters: payload.
        Returns: review requiring reconsideration. Failures: none.
        """
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue()]}

    def reconsider(payload):
        """Purpose: assess the original objection without changing prose. Parameters: payload.
        Returns: PASS. Failures: assertions if rubric or current-draft context is absent.
        """
        assert payload["prior_review"]["verdict"] == "REVIEW_REQUIRED"
        assert payload["draft"] == entry()
        assert payload["revision"] == 0 and payload["discussion"] == {}
        instruction = payload["review_instruction"]
        assert "substantive factual errors" in instruction
        assert "Sanskrit grammatical errors" in instruction
        assert "chapter-title word" in instruction and "Do NOT force PASS" in instruction
        payload["draft"]["new_sutra"] = "Unauthorized edit"
        payload["prior_review"]["issues"].clear()
        return {"verdict": "PASS", "issues": []}

    fake = FakeCallbacks({"independent_review": original,
                          "independent_review_reconsideration": reconsider})
    result = fake.council(tmp_path, 1).run(*inputs())
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW" and result["revisions"] == 0
    assert result["draft"] == entry()
    assert len(fake.calls) == 20
    assert [p["stage"] for p in fake.calls if p["stage"].startswith("composition")] == ["composition"]
    assert [r["stage"] for r in result["review_history"]] == [
        "independent_review", "independent_review_reconsideration"]
    assert result["review_history"][0]["review"]["issues"] == [issue()]
    fake.calls.clear()
    assert fake.council(tmp_path, 1).run(*inputs()) == result
    assert fake.calls == []


def test_reconsideration_is_once_per_entry_and_does_not_force_pass(tmp_path):
    """Purpose: bound failed reconsideration and Claude repairs. Parameters: tmp_path.
    Returns: None. Failures: assertions for a second reconsideration or false PASS.
    """
    def review(payload):
        """Purpose: retain a genuine current defect. Parameters: payload.
        Returns: REVIEW_REQUIRED. Failures: none.
        """
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue()]}

    fake = FakeCallbacks({"validator": review})
    result = fake.council(tmp_path, 1).run(*inputs())
    counts = Counter(p["stage"] for p in fake.calls)
    assert result["status"] == "NEEDS_REVIEW" and result["revisions"] == 1
    assert counts["independent_review_reconsideration"] == 1
    assert counts["composition"] == counts["composition_1"] == 1
    assert [r["stage"] for r in result["review_history"]] == [
        "independent_review", "independent_review_reconsideration", "independent_review_1"]
    assert len(fake.calls) == 23
    fake.calls.clear()
    assert fake.council(tmp_path, 1).run(*inputs()) == result
    assert fake.calls == []


def test_reconsideration_of_saved_current_revision_never_resurrects_old_composition(tmp_path):
    """Purpose: recover an existing quality stop using only the fifth reviewer.
    Parameters: tmp_path. Returns: None. Failures: assertions for Claude replay,
    obsolete review, lost previous reviews, or altered saved input hashes.
    """
    def review(payload):
        """Purpose: reproduce the previous policy's quality stop. Parameters: payload.
        Returns: a quote grounded in whichever draft is current. Failures: none.
        """
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue(quote=payload["draft"]["new_sutra"])]}

    def repaired(payload):
        """Purpose: return a distinguishable second draft. Parameters: payload.
        Returns: repaired complete entry. Failures: none.
        """
        return entry("सत्यं व्यवसायस्य मूलम्")

    def legacy_review_policy(*args, **kwargs):
        """Purpose: simulate pre-feature checkpoints. Parameters: ignored arguments.
        Returns: None, with no reconsideration. Failures: none.
        """
        return None

    fake = FakeCallbacks({"validator": review, "composition_1": repaired})
    legacy = fake.council(tmp_path, 1)
    legacy._reconsider_review = legacy_review_policy
    stopped = legacy.run(*inputs())
    assert stopped["status"] == "NEEDS_REVIEW" and stopped["revisions"] == 1
    with sqlite3.connect(legacy.path) as db:
        stages_before = db.execute("SELECT * FROM research_stages").fetchall()
        runs_before = db.execute("SELECT * FROM research_runs").fetchall()

    def reconsider(payload):
        """Purpose: review only the saved latest draft. Parameters: payload.
        Returns: warranted PASS. Failures: assertions on stale/current mismatch.
        """
        assert payload["revision"] == 1
        assert payload["draft"] == stopped["draft"]
        assert payload["prior_review"] == stopped["review"]
        return {"verdict": "PASS", "issues": []}

    fake.overrides["independent_review_reconsideration"] = reconsider
    fake.calls.clear()
    result = fake.council(tmp_path, 1).run(*inputs())
    assert [(p["stage"], p["speaker"]) for p in fake.calls] == [
        ("independent_review_reconsideration", "validator")]
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW" and result["revisions"] == 1
    assert result["draft"] == stopped["draft"]
    assert [(r["stage"], r["revision"]) for r in result["review_history"]] == [
        ("independent_review", 0), ("independent_review_1", 1),
        ("independent_review_reconsideration", 1)]
    with sqlite3.connect(legacy.path) as db:
        stages_after = db.execute("SELECT * FROM research_stages").fetchall()
        assert all(row in stages_after for row in stages_before)
        assert db.execute("SELECT * FROM research_runs").fetchall() == runs_before
        assert db.execute("SELECT revision FROM research_reconsiderations").fetchall() == [(1,)]
    fake.calls.clear()
    assert fake.council(tmp_path, 1).run(*inputs()) == result
    assert fake.calls == []


@pytest.mark.parametrize("defect", ["absent_quote", "edited_draft"])
def test_reconsideration_rejects_invalid_review_once_and_preserves_saved_draft(tmp_path, defect):
    """Purpose: preserve quote/edit rules with a one-call budget. Parameters: tmp_path, defect.
    Returns: None. Failures: assertions for additional calls or invalid acceptance.
    """
    def review(payload):
        """Purpose: provide a valid initial concern. Parameters: payload.
        Returns: original review. Failures: none.
        """
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue()]}

    def invalid(payload):
        """Purpose: test reconsideration constraints. Parameters: payload.
        Returns: invalid quote or edit. Failures: none; council must reject.
        """
        if defect == "edited_draft":
            return {"verdict": "PASS", "issues": [], "edited_draft": entry("Different text")}
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue(quote="Absent old proposal")]}

    fake = FakeCallbacks({"independent_review": review, "independent_review_reconsideration": invalid})
    with pytest.raises(ValueError, match="Invalid review"):
        fake.council(tmp_path, 1).run(*inputs())
    assert Counter(p["stage"] for p in fake.calls)["independent_review_reconsideration"] == 1
    assert [p["stage"] for p in fake.calls if p["stage"].startswith("composition")] == ["composition"]
    with sqlite3.connect(tmp_path / "research.db") as db:
        saved = db.execute("SELECT response_json FROM research_stages WHERE stage='composition'").fetchone()[0]
    assert json.loads(saved) == entry()
    fake.calls.clear()
    with pytest.raises(ValueError, match="Exhausted independent_review_reconsideration"):
        fake.council(tmp_path, 1).run(*inputs())
    assert fake.calls == []


def policy_stop(tmp_path, number=8, assessment_pass=True):
    """Purpose: reproduce saved final-review holds. Parameters: tmp_path, number,
    assessment_pass. Returns: fake callbacks, args, stopped result. Failures:
    fixture/council errors propagate; no real provider or production DB is used.
    """
    def held(payload):
        """Purpose: retain a grounded review hold. Parameters: payload.
        Returns: REVIEW_REQUIRED. Failures: none.
        """
        return {"verdict": "REVIEW_REQUIRED", "issues": [issue(quote=payload["draft"]["new_sutra"])]}

    def repair(payload):
        """Purpose: distinguish latest draft from the original. Parameters: payload.
        Returns: complete repaired fixture. Failures: none.
        """
        return entry("सत्यं व्यवसायस्य मूलम्", payload["number"])

    def assess(payload):
        """Purpose: control deterministic eligibility. Parameters: payload.
        Returns: explicit assessment. Failures: none.
        """
        return {"status": "PASS" if assessment_pass else "NEEDS_REVISION",
                "issues": [] if assessment_pass else ["Missing source evidence"]}

    fake = FakeCallbacks({"validator": held, "composition_1": repair, "assessor": assess})
    args = inputs(number)
    stopped = fake.council(tmp_path, 1).run(*args)
    assert stopped["status"] == "NEEDS_REVIEW" and stopped["revisions"] == 1
    fake.calls.clear()
    return fake, args, stopped


@pytest.mark.parametrize("number", [5, 8, 9])
def test_policy_correction_current_saved_draft_one_validator_call_and_cached_replay(tmp_path, number):
    """Purpose: recover only explicitly listed holds. Parameters: tmp_path, number.
    Returns: None. Failures: assertions for Claude replay, changed hashes/drafts,
    lost old reviews or correction calls on obsolete drafts.
    """
    fake, args, stopped = policy_stop(tmp_path, number)
    reason = "Mixed classical/author ledger caused broad thematic rejection"
    with sqlite3.connect(tmp_path / "research.db") as db:
        old_stages = db.execute("SELECT * FROM research_stages").fetchall()
        old_runs = db.execute("SELECT * FROM research_runs").fetchall()

    def corrected(payload):
        """Purpose: evaluate corrected policy without editing. Parameters: payload.
        Returns: warranted PASS. Failures: assertions for missing rubric or stale draft.
        """
        assert payload["revision"] == 1 and payload["draft"] == stopped["draft"]
        assert payload["prior_review"] == stopped["review"]
        assert payload["policy_correction_reason"] == reason
        rubric = payload["review_instruction"]
        assert "Reject exact or normalized copying" in rubric
        assert "classical thematic inheritance" in rubric
        assert "material duplication of the same business decision" in rubric
        assert "not merely a broad shared theme" in rubric
        assert "Do NOT force PASS" in rubric
        payload["draft"]["new_sutra"] = "Unauthorized edit"
        payload["prior_review"]["issues"].clear()
        return {"verdict": "PASS", "issues": []}

    fake.overrides["independent_review_policy_correction_v1"] = corrected
    result = fake.council(tmp_path, 1, {number: reason}).run(*args)
    assert [(p["stage"], p["speaker"]) for p in fake.calls] == [
        ("independent_review_policy_correction_v1", "validator")]
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW" and result["revisions"] == 1
    assert result["draft"] == stopped["draft"]
    assert result["review_history"][:-1] == stopped["review_history"]
    assert result["review_history"][-1] == {
        "stage": "independent_review_policy_correction_v1", "revision": 1,
        "review": {"verdict": "PASS", "issues": []}}
    with sqlite3.connect(tmp_path / "research.db") as db:
        now = db.execute("SELECT * FROM research_stages").fetchall()
        assert all(row in now for row in old_stages)
        assert db.execute("SELECT * FROM research_runs").fetchall() == old_runs
    fake.calls.clear()
    assert fake.council(tmp_path, 1, {number: reason}).run(*args) == result
    assert fake.calls == []


@pytest.mark.parametrize("eligible_assessment,whitelist", [(False, {8: "Diagnostic"}), (True, {5: "Diagnostic"})])
def test_policy_correction_requires_whitelist_and_assessment_pass(tmp_path, eligible_assessment, whitelist):
    """Purpose: fail closed on ineligible entries. Parameters: tmp_path, assessment, whitelist.
    Returns: None. Failures: assertions for any new callback or altered outcome.
    """
    fake, args, stopped = policy_stop(tmp_path, assessment_pass=eligible_assessment)
    assert fake.council(tmp_path, 1, whitelist).run(*args) == stopped
    assert fake.calls == []


def test_policy_correction_does_not_review_already_passing_entry(tmp_path):
    """Purpose: avoid unnecessary review cost. Parameters: tmp_path. Returns: None.
    Failures: assertions if a PASS triggers correction despite explicit mapping.
    """
    fake = FakeCallbacks()
    result = fake.council(tmp_path, 1, {8: "Diagnostic"}).run(*inputs(8))
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW" and len(fake.calls) == 19
    assert len(result["review_history"]) == 1


def test_policy_correction_may_remain_required_and_cannot_reopen_with_a_new_reason(tmp_path):
    """Purpose: preserve validator independence and one-shot scope. Parameters: tmp_path.
    Returns: None. Failures: assertions for forced PASS, repeat calls or changed-reason reuse.
    """
    fake, args, stopped = policy_stop(tmp_path)
    result = fake.council(tmp_path, 1, {8: "Diagnostic"}).run(*args)
    assert result["status"] == "NEEDS_REVIEW" and result["draft"] == stopped["draft"]
    assert [p["stage"] for p in fake.calls] == ["independent_review_policy_correction_v1"]
    fake.calls.clear()
    assert fake.council(tmp_path, 1, {8: "Diagnostic"}).run(*args) == result
    with pytest.raises(ValueError, match="Stale request"):
        fake.council(tmp_path, 1, {8: "Different justification is not a v2"}).run(*args)
    assert fake.calls == []


@pytest.mark.parametrize("defect", ["old_quote", "edited_draft", "bad_verdict"])
def test_policy_correction_failure_is_terminal_after_one_call(tmp_path, defect):
    """Purpose: retain strict reviewer schemas and one-call bound. Parameters: tmp_path, defect.
    Returns: None. Failures: assertions for retry expansion or editing acceptance.
    """
    fake, args, stopped = policy_stop(tmp_path)

    def malformed(payload):
        """Purpose: provide an invalid policy-review result. Parameters: payload.
        Returns: old quotation, edit, or invalid verdict. Failures: none.
        """
        if defect == "old_quote":
            return {"verdict": "REVIEW_REQUIRED", "issues": [issue()]}
        if defect == "edited_draft":
            return {"verdict": "PASS", "issues": [], "draft": entry()}
        return {"verdict": "APPROVED", "issues": []}

    fake.overrides["independent_review_policy_correction_v1"] = malformed
    council = fake.council(tmp_path, 1, {8: "Diagnostic"})
    with pytest.raises(ValueError, match="Invalid review"):
        council.run(*args)
    assert [p["stage"] for p in fake.calls] == ["independent_review_policy_correction_v1"]
    fake.calls.clear()
    with pytest.raises(ValueError, match="Exhausted independent_review_policy_correction_v1"):
        fake.council(tmp_path, 1, {8: "Diagnostic"}).run(*args)
    with pytest.raises(ValueError, match="exactly two matching FAILED"):
        council.authorize_schema_retry(8, "independent_review_policy_correction_v1", "validator", "No second correction")
    assert fake.calls == []
    with sqlite3.connect(council.path) as db:
        saved = json.loads(db.execute("SELECT response_json FROM research_stages WHERE number=8 AND stage='composition_1'").fetchone()[0])
    assert saved == stopped["draft"]


@pytest.mark.parametrize("mapping", [[], {0: "reason"}, {True: "reason"}, {"8": "reason"}, {8: " "}, {8: None}])
def test_policy_correction_configuration_requires_explicit_positive_keys_and_reasons(tmp_path, mapping):
    """Purpose: reject ambiguous recovery configuration. Parameters: tmp_path, mapping.
    Returns: None. Failures: assertions for malformed or implicit authorization.
    """
    with pytest.raises(ValueError, match="policy_corrections"):
        FakeCallbacks().council(tmp_path, 1, mapping)


def test_policy_correction_preserves_existing_entry_input_guards(tmp_path):
    """Purpose: prevent changed evidence from using recovery. Parameters: tmp_path.
    Returns: None. Failures: assertions if opt-in bypasses existing request hashes.
    """
    fake, args, _ = policy_stop(tmp_path)
    changed = list(deepcopy(args))
    changed[2]["new_evidence"] = "Changed source packet"
    with pytest.raises(ValueError, match="Stale inputs"):
        fake.council(tmp_path, 1, {8: "Diagnostic"}).run(*changed)
    assert fake.calls == []

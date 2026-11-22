"""Fake-only selection/rejection and legacy checkpoint compatibility checks.

No providers, credentials or semantic quality certification. Existing council
fixtures retain full four-voice barriers and an independently bound validator.
"""

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from src.orchestration.research_council import ResearchCouncil, SOURCE_FIRST_SELECTION, VOICES
from tests.test_research_council import FakeCallbacks, batch_inputs, entry, inputs


REASON = "या स्रोतांमध्ये प्रस्तावित व्यवसायनियमासाठी पुरेसा आधार मिळत नाही"


def source_inputs(numbers=(1, 2)):
    """Return synthetic numbered pair packets; no real source evidence is asserted."""
    args = list(batch_inputs(numbers))
    args[2] = {str(n): {"source_pair_ids": [f"N{n}", f"S{n}"],
                       "references": [{"id": f"N{n}", "original_text": "Synthetic Narada"},
                                      {"id": f"S{n}", "original_text": "Synthetic Shandilya"},
                                      {"id": "E1", "original_text": "Synthetic external"}]}
               for n in numbers}
    return args


def selection_fakes(rejected=(2,), parallel=False):
    """Reuse actual round fixtures, changing only Sutrakar's proposal/composition."""
    fake = FakeCallbacks(parallel=parallel)

    def propose(payload):
        """Accept or decline each input only after every voice's three rounds."""
        assert set(payload["discussion"]) == {"position", "challenge", "reply"}
        assert payload["source_first_selection"] == SOURCE_FIRST_SELECTION
        proposals = []
        for n in payload["entry_numbers"]:
            if n in rejected:
                proposals.append({"number": n, "decision": "REJECT", "rejection_reason": REASON})
            else:
                proposals.append({"number": n, "decision": "ACCEPT",
                                  "proposed_sutra": "उद्यमेन विवेकः", "derivation": "Synthetic derivation",
                                  "selected_source_ids": [f"N{n}", f"S{n}", "E1"]})
        return {"proposals": proposals}

    def compose(payload):
        """Return a complete parent-enriched fixture only for an accepted input."""
        assert payload["proposal"]["decision"] == "ACCEPT"
        result = entry(number=payload["number"])
        result["references"] = payload["proposal"]["selected_source_ids"]
        return result

    fake.overrides.update(proposal=propose, composition=compose)
    return fake


def council(path, fake, **kwargs):
    """Construct the opt-in council with fake callbacks, leaving legacy options intact."""
    return ResearchCouncil(path / "research.db", fake.voices, fake.validator, fake.assessor,
                           source_first_selection=True, **kwargs)


def compose_selected(instance, args, result, index=0, selected_only=False):
    """Mirror the parent's accepted-entry handoff, using full or selected records."""
    brief, number = args[1][index], args[1][index]["number"]
    proposal, peers = result["proposal"], result["peer_review"]
    if selected_only:
        proposal = next(p for p in proposal["proposals"] if p["number"] == number)
        peers = {role: next(r for r in value["reviews"] if r["number"] == number)
                 for role, value in peers.items()}
    return instance.compose_entry(number, brief, args[2][str(number)], args[3], args[4], set(),
                                  result["discussion"], proposal, peers)


@pytest.mark.parametrize("selected_only", [False, True])
def test_four_voices_discuss_rejection_and_only_accepted_entry_composes(tmp_path, selected_only):
    """All rounds occur once; accepted entries retain independent validation and resume."""
    fake, args = selection_fakes(parallel=True), source_inputs()
    instance = council(tmp_path, fake)
    before = deepcopy(args)
    batch = instance.run_batch_discussion(*args)
    assert batch["accepted_numbers"] == [1] and batch["rejected_numbers"] == [2]
    assert "proposed_sutra" not in batch["proposal"]["proposals"][1]
    assert Counter(p["stage"] for p in fake.calls) == {
        "position": 4, "challenge": 4, "reply": 4, "proposal": 1, "peer_review": 3}
    for stage in ("position", "challenge", "reply"):
        assert set(batch["discussion"][stage]) == set(VOICES)
    for stage, field in (("challenge", "challenges"), ("reply", "answers")):
        for voice in VOICES:
            assert set(batch["discussion"][stage][voice][field]) == set(VOICES) - {voice}
            assert all(set(items) == {"1", "2"}
                       for items in batch["discussion"][stage][voice][field].values())
    result = compose_selected(instance, args, batch, selected_only=selected_only)
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW"
    assert set(result["draft"]["references"]) == {"N1", "S1", "E1"}
    validator = [p for p in fake.calls if p.get("speaker") == "validator"]
    assert len(validator) == 1 and validator[0]["number"] == 1
    assert validator[0]["discussion"] == {}
    assert "proposal" not in validator[0] and "peer_review" not in validator[0]
    assert len(fake.calls) == 19
    with pytest.raises(ValueError, match="skip composition"):
        compose_selected(instance, args, batch, index=1, selected_only=selected_only)
    assert len(fake.calls) == 19 and args == before
    fake.calls.clear()
    resumed = council(tmp_path, fake)
    cached = resumed.run_batch_discussion(*args)
    assert cached == batch
    assert compose_selected(resumed, args, cached, selected_only=selected_only) == result
    assert fake.calls == []


def test_all_rejected_with_peer_objection_never_forces_formula_or_repeats_discussion(tmp_path):
    """Peers can question an exact decline reason without converting it into a draft."""
    fake, args = selection_fakes(rejected=(1, 2)), source_inputs()

    def review(payload):
        """Ground one peer objection in the actual rejection; other peers may PASS."""
        return {"reviews": [{"number": n, "verdict": "REVIEW_REQUIRED", "issues": [{
            "field": "rejection_reason", "quote": REASON,
            "reason": "Consider whether the second source provides a narrower justification",
            "severity": "major"}]} for n in payload["entry_numbers"]]}

    fake.overrides[("peer_review", "narada")] = review
    result = council(tmp_path, fake).run_batch_discussion(*args)
    assert result["accepted_numbers"] == [] and result["rejected_numbers"] == [1, 2]
    assert result["peer_review"]["narada"]["reviews"][0]["verdict"] == "REVIEW_REQUIRED"
    assert len(fake.calls) == 16
    fake.calls.clear()
    assert council(tmp_path, fake).run_batch_discussion(*args) == result
    assert fake.calls == []
    with sqlite3.connect(result["checkpoint_path"]) as db:
        assert db.execute("SELECT COUNT(*) FROM research_attempts").fetchone()[0] == 16
        assert db.execute("SELECT DISTINCT state FROM research_attempts").fetchall() == [("COMPLETE",)]


@pytest.mark.parametrize("defect", ["missing_reason", "short_reason", "formula", "missing_decision"])
def test_rejection_requires_explanatory_reason_and_no_formula(tmp_path, defect):
    """Invalid declines consume only normal schema attempts, never repeat debate."""
    fake, args = selection_fakes(rejected=(1,)), source_inputs((1,))
    original = fake.overrides["proposal"]

    def malformed(payload):
        """Return one specific invalid disposition without any provider calls."""
        result = original(payload)
        proposal = result["proposals"][0]
        if defect == "missing_reason":
            proposal.pop("rejection_reason")
        elif defect == "short_reason":
            proposal["rejection_reason"] = "Not suitable"
        elif defect == "formula":
            proposal["proposed_sutra"] = "उद्यमेन विवेकः"
        else:
            proposal.pop("decision")
        return result

    fake.overrides["proposal"] = malformed
    with pytest.raises(ValueError, match="Exhausted proposal"):
        council(tmp_path, fake).run_batch_discussion(*args)
    assert Counter(p["stage"] for p in fake.calls) == {
        "position": 4, "challenge": 4, "reply": 4, "proposal": 2}
    fake.calls.clear()
    with pytest.raises(ValueError, match="Exhausted proposal"):
        council(tmp_path, fake).run_batch_discussion(*args)
    assert fake.calls == []


@pytest.mark.parametrize("patch", [
    {"proposed_sutra": None}, {"proposed_sutra": "एकम्"},
    {"proposed_sutra": "one two three four five"},
    {"proposed_sutra": "अ" * 31 + " ब"},
    {"selected_source_ids": []}, {"selected_source_ids": ["N1"]},
    {"selected_source_ids": ["N1", "S2"]},
    {"selected_source_ids": ["N1", "S1", "invented"]},
    {"selected_source_ids": ["N1", "S1", "S1"]},
    {"derivation": ""}, {"rejection_reason": REASON},
])
def test_acceptance_retains_short_formula_derivation_and_exact_pair_gates(tmp_path, patch):
    """Source-first opt-in cannot weaken the accepted-proposal constraints."""
    fake, args = selection_fakes(rejected=()), source_inputs((1,))
    original = fake.overrides["proposal"]

    def malformed(payload):
        """Alter only the acceptance field under test."""
        result = original(payload)
        result["proposals"][0].update(patch)
        return result

    fake.overrides["proposal"] = malformed
    with pytest.raises(ValueError, match="Exhausted proposal"):
        council(tmp_path, fake).run_batch_discussion(*args)
    assert not any(p["stage"] in ("peer_review", "composition", "independent_review") for p in fake.calls)


def test_missing_pair_packet_rejected_before_any_callback(tmp_path):
    """The caller must declare source-pair references before funding discussion."""
    fake = selection_fakes()
    with pytest.raises(ValueError, match="source_pair_ids"):
        council(tmp_path, fake).run_batch_discussion(*batch_inputs((1,)))
    assert fake.calls == []


def test_default_still_rejects_missing_formula_despite_reject_label(tmp_path):
    """REJECT has no special meaning under the unchanged default batch protocol."""
    def proposal(payload):
        """Return a decline without the mandatory legacy short formula."""
        assert "source_first_selection" not in payload
        return {"proposals": [{"number": n, "decision": "REJECT", "rejection_reason": REASON}
                              for n in payload["entry_numbers"]]}

    fake = FakeCallbacks({"proposal": proposal})
    with pytest.raises(ValueError, match="Short-sutra"):
        fake.council(tmp_path).run_batch_discussion(*batch_inputs((1,)))
    assert Counter(p["stage"] for p in fake.calls) == {
        "position": 4, "challenge": 4, "reply": 4, "proposal": 2}


def legacy_json(value):
    """Serialize the pre-change protocol literally, independently of production helpers."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def seed_legacy_batch(instance, fake, args):
    """Seed all sixteen pre-change successful requests using the exact v3 base.

    No modified council method generates these hashes; a policy key or protocol
    change would reject them or trigger a callback in the compatibility test.
    """
    batch_id, briefs, packets, prior, forbidden = args
    numbers = [b["number"] for b in briefs]
    base = {"number": 0, "brief": {"batch_id": batch_id}, "sources": packets,
            "scope": "batch", "batch_id": batch_id, "briefs": briefs,
            "entry_numbers": numbers, "sources_by_entry": packets,
            "prior_formulas": prior, "forbidden_originals": forbidden, "used_case_ids": []}
    digest = hashlib.sha256(legacy_json(batch_id).encode()).hexdigest()
    path = instance.path.with_name(f"{instance.path.name}.batch-{digest}.sqlite3")
    ResearchCouncil(path, fake.voices, fake.validator, fake.assessor)
    discussion, rows = {}, []
    for stage in ("position", "challenge", "reply", "proposal", "peer_review"):
        answers = {}
        speakers = ("sutrakar",) if stage == "proposal" else VOICES[:-1] if stage == "peer_review" else VOICES
        for speaker in speakers:
            request = {**base, "discussion": discussion, "stage": stage, "speaker": speaker}
            if stage == "peer_review":
                request["proposal"] = proposal
            answer = fake.batch_answer(request)
            rows.append((0, stage, speaker, hashlib.sha256(legacy_json(request).encode()).hexdigest(),
                         legacy_json(answer)))
            answers[speaker] = answer
        if stage in ("position", "challenge", "reply"):
            discussion[stage] = answers
        elif stage == "proposal":
            proposal = answers["sutrakar"]
    run_hash = hashlib.sha256(legacy_json({**base, "max_revisions": 2, "protocol": 3}).encode()).hexdigest()
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO research_runs VALUES (?,?)", (0, run_hash))
        db.executemany("INSERT INTO research_stages VALUES (?,?,?,?,?)", rows)
    return path, run_hash, rows


@pytest.mark.parametrize("explicit_default", [False, True])
def test_prechange_cached_inputs_and_stage_hashes_remain_unchanged(tmp_path, explicit_default):
    """Literal legacy v3 checkpoints replay with no callbacks and no new policy data."""
    fake, args = FakeCallbacks(), batch_inputs((1, 2))
    kwargs = {"source_first_selection": False} if explicit_default else {}
    instance = ResearchCouncil(tmp_path / "research.db", fake.voices, fake.validator, fake.assessor, **kwargs)
    path, run_hash, rows = seed_legacy_batch(instance, fake, args)
    result = instance.run_batch_discussion(*args)
    assert fake.calls == []
    assert "source_first_selection" not in result["discussion"]["_batch"]
    assert "accepted_numbers" not in result and "rejected_numbers" not in result
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT request_hash FROM research_runs").fetchone()[0] == run_hash
        assert sorted(db.execute("SELECT * FROM research_stages").fetchall()) == sorted(rows)
        assert db.execute("SELECT COUNT(*) FROM research_attempts").fetchone()[0] == 0


@pytest.mark.parametrize("initial_opt_in", [False, True])
def test_policy_toggle_cannot_reuse_batch_checkpoint_or_selection(tmp_path, initial_opt_in):
    """Changing selection policy stops before any new discussion or composition call."""
    args = source_inputs((1,))
    fake = selection_fakes(rejected=()) if initial_opt_in else FakeCallbacks()
    original = council(tmp_path, fake) if initial_opt_in else fake.council(tmp_path)
    batch = original.run_batch_discussion(*args)
    fake.calls.clear()
    changed = fake.council(tmp_path) if initial_opt_in else council(tmp_path, fake)
    with pytest.raises(ValueError, match="Stale inputs"):
        changed.run_batch_discussion(*args)
    with pytest.raises(ValueError, match="policy mismatch"):
        compose_selected(changed, args, batch)
    assert fake.calls == []


def test_single_entry_opt_in_requires_explicit_batch_handoff(tmp_path):
    """The new policy does not silently change the legacy single-entry protocol."""
    fake = selection_fakes()
    with pytest.raises(ValueError, match="run_batch_discussion"):
        council(tmp_path, fake).run(*inputs())
    assert fake.calls == []

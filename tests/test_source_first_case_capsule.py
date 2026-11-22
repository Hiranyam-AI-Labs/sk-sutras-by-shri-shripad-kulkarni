"""Offline capsule integrity/council regressions; fake callbacks, synthetic facts.

These tests certify structural routing and cache isolation only, never semantic
case fit or historical truth. No SDK, credential loader, network or paid call.
"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import prepare_source_first_book as preparation
from src.orchestration.source_first_case_capsule import (
    POOL, OVERLAY, apply_case_capsule, bind_composition_view, build_case_capsule,
    composition_scope, digest,
)
from src.orchestration.research_council import ResearchCouncil, VOICES
from tests.test_source_first_book_plan import fixture, PROSE
from tests.test_source_first_council import council, selection_fakes, source_inputs
from tests.test_research_council import FakeCallbacks, batch_inputs, entry


def write_json(path, value):
    """Write synthetic JSON proof bytes and return their SHA256."""
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    path.write_bytes(raw)
    return preparation.byte_hash(raw)


def case_work(path, *, change=None, statuses=None, identity_hold=None, relations=()):
    """Build a genuine four-shard merge on temporary synthetic evidence only."""
    path.mkdir()
    inputs = fixture()
    pool = inputs["case_pool"]
    if change:
        change(pool)
    pool_sha = write_json(path / POOL, pool)
    first = pool["cases"][0]
    original = {"fact_verifications": [{
        "case_id": first["case_id"], "status": "MATCH",
        "case_pool_record_sha256": digest(first),
        "existing_text_mr_sha256": preparation.byte_hash(first["text_mr"].encode()),
        "existing_recorded_fact_sha256": preparation.byte_hash(first["recorded_fact"].encode()),
        "exact_supported_fact": "Synthetic original proof; no historical claim.",
        "limitations_mr": PROSE,
    }], "identity_verifications": [], "cross_case_relationships": [],
        "input_bindings": [{"path": POOL, "sha256": pool_sha}]}
    cases = {c["case_id"]: c for c in pool["cases"]}
    if identity_hold:
        original["identity_verifications"].append({
            "case_id": identity_hold, "case_pool_record_sha256": digest(cases[identity_hold]),
            "status": "HOLD", "verified_relationships": [], "reason_mr": PROSE})
    for ids in relations:
        original["cross_case_relationships"].append({
            "case_ids": list(ids), "case_record_bindings": {i: digest(cases[i]) for i in ids},
            "reason_mr": PROSE})
    original_sha = write_json(path / "business-case-verification-overlay.json", original)
    for shard in range(4):
        records = [{"case_id": c["case_id"], "canonicalcasehash": digest(c),
                    "status": (statuses or {}).get(c["case_id"], "QUALIFIED"),
                    "primary_urls": ["https://example.org/synthetic-proof"],
                    "checked_date_local": "2026-11-21", "exact_supported_fact": "Synthetic only.",
                    "reason_mr": PROSE, "limitations_mr": "Fixture limitation: retain this qualification."}
                   for i, c in enumerate(pool["cases"]) if i % 4 == shard and i != 0]
        write_json(path / f"business-case-fresh-shard-{shard}.json", {
            "status": "COMPLETE", "shard_index": shard, "records": records,
            "pool_sha256": pool_sha, "excluded_overlay_sha256": original_sha})
    write_json(path / OVERLAY, preparation.prepare_complete_case_overlay(path))
    return path


@pytest.fixture
def setup(tmp_path, request):
    """Run actual four-voice fake deliberation before attaching any cases."""
    fake, args = selection_fakes(parallel=True), source_inputs()
    held_role = getattr(request, "param", None)
    if held_role is not None:
        def held_review(payload):
            """Return a well-formed original objection during the actual peer round."""
            result = fake.batch_answer(payload)
            result["reviews"][0].update(verdict="REVIEW_REQUIRED", issues=[{
                "field": "derivation", "quote": "Synthetic derivation",
                "reason": "Synthetic unresolved source-support objection", "severity": "major"}])
            return result
        fake.overrides[("peer_review", held_role)] = held_review
    for packet in args[2].values():
        packet.update(examples=[], source_contexts={"N1": {"context_mr": "Original limits remain exact"}},
                      selection_provenance={"card": "Original hypothesis"})
    instance = council(tmp_path / "council", fake)
    batch = instance.run_batch_discussion(*args)
    selection = dict(number=1, brief=args[1][0], sources=args[2]["1"],
                     discussion=batch["discussion"], proposal=batch["proposal"],
                     peer_review=batch["peer_review"])
    return dict(fake=fake, args=args, instance=instance, batch=batch, selection=selection,
                work=case_work(tmp_path / "proofs"), tmp_path=tmp_path)


def construct(setup, **changes):
    """Build the public capsule using exact existing selection and empty usage."""
    args = dict(**setup["selection"], case_work_dir=setup["work"], used_case_ids=set(),
                case_slots=[{"kind": "positive", "case_id": "positive-a", "fit_reason_mr": PROSE,
                             "limitations_mr": "Positive fit is a limited analogy; " + PROSE},
                            {"kind": "caution", "case_id": "caution-b", "fit_reason_mr": PROSE,
                             "limitations_mr": "Caution fit is a limited analogy; " + PROSE}])
    args.update(changes)
    return build_case_capsule(**args)


def compose(setup, capsule, **changes):
    """Call the public council seam, never private compose or checkpoint edits."""
    args = dict(**setup["selection"], prior_formulas=setup["args"][3],
                forbidden_originals=setup["args"][4], used_case_ids=set(), case_capsule=capsule)
    args.update(changes)
    return setup["instance"].compose_entry(**args)


def reseal(capsule):
    """Recompute only the outer envelope to exercise deeper integrity gates."""
    capsule["capsule_sha256"] = digest({k: v for k, v in capsule.items() if k != "capsule_sha256"})


def replace_snapshot_document(snapshot, document):
    """Change snapshot bytes with a consistent inner hash, not its bound proofs."""
    raw = json.dumps(document, ensure_ascii=False).encode()
    snapshot.update(raw_json=raw.decode(), bytes=len(raw), sha256=preparation.byte_hash(raw))


def test_two_case_attachment_retains_selection_and_proofs_without_redebate(setup):
    """Cases enrich only composition; four voices/peer reviews remain exact and reusable."""
    before = deepcopy(setup["selection"])
    original_files = {p.name: p.read_bytes() for p in setup["work"].iterdir()}
    capsule = construct(setup)
    effective, binding = apply_case_capsule(capsule, **setup["selection"], used_case_ids=set())
    original = setup["selection"]["sources"]
    assert {k: v for k, v in effective.items() if k not in (
        "examples", "case_assignments", "case_capsule_provenance")} == {
            k: v for k, v in original.items() if k != "examples"}
    assert [c["kind"] for c in effective["examples"]] == ["positive", "caution"]
    assignment = effective["case_assignments"][1]
    assert assignment["verification"]["status"] == "QUALIFIED"
    assert "existing_marathi_material_fact_contradiction_found" not in assignment["verification"]
    assert assignment["verification"]["limitations_mr"].startswith("Fixture limitation")
    assert assignment["limitations_mr"] == capsule["case_slots"][1]["limitations_mr"]
    assert binding["original_selection_sha256"] == capsule["selection"]["selection_sha256"]
    assert binding["case_capsule_sha256"] == capsule["capsule_sha256"]
    result = compose(setup, capsule)
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW"
    calls = setup["fake"].calls
    assert Counter(p["stage"] for p in calls) == {
        "position": 4, "challenge": 4, "reply": 4, "proposal": 1, "peer_review": 3,
        "composition": 1, "assessor": 1, "independent_review": 1}
    for call in calls:
        if call["stage"] in ("composition", "independent_review"):
            assert call["sources"] == effective and call["composition_binding"] == binding
        elif call["stage"] == "assessor":
            assert call["sources"] == effective
    reviewer = next(p for p in calls if p["stage"] == "independent_review")
    assert reviewer["discussion"] == {} and "proposal" not in reviewer
    assert setup["selection"] == before
    assert {p.name: p.read_bytes() for p in setup["work"].iterdir()} == original_files
    setup["fake"].calls.clear()
    assert setup["instance"].run_batch_discussion(*setup["args"]) == setup["batch"]
    assert compose(setup, json.loads(json.dumps(capsule))) == result
    assert setup["fake"].calls == []


@pytest.mark.parametrize("field", ["brief", "sources", "proposal", "discussion", "peer_review"])
def test_exact_accepted_selection_binding_rejects_changed_inputs_before_callbacks(setup, field):
    capsule = construct(setup)
    changed = deepcopy(setup["selection"][field])
    if field == "proposal":
        changed["proposals"][0]["derivation"] = "A changed accepted derivation"
    elif field == "discussion":
        changed["position"]["narada"]["positions"]["1"]["thesis"] = "Changed position"
    elif field == "peer_review":
        changed["narada"]["reviews"][0]["verdict"] = "REVIEW_REQUIRED"
        changed["narada"]["reviews"][0]["issues"] = [
            {"field": "derivation", "quote": "Synthetic derivation", "reason": "Changed issue", "severity": "minor"}]
    else:
        changed["unauthorized"] = "changed"
    count = len(setup["fake"].calls)
    with pytest.raises(ValueError):
        compose(setup, capsule, **{field: changed})
    assert len(setup["fake"].calls) == count


@pytest.mark.parametrize("patch", ["sources", "brief", "proposal", "selection_provenance", "examples"])
def test_capsule_is_not_arbitrary_packet_patch_even_with_new_outer_hash(setup, patch):
    capsule = construct(setup)
    capsule[patch] = {"changed": True}
    reseal(capsule)
    with pytest.raises(ValueError, match="Exact case capsule"):
        compose(setup, capsule)


@pytest.mark.parametrize("kind", ["capsule_hash", "pool_bytes", "overlay_bytes", "proof_bytes",
                                  "selection_hash", "pair", "usage", "slot_extra", "fit_empty", "limits_empty"])
def test_tampered_capsule_fails_before_composition(setup, kind):
    capsule = construct(setup)
    if kind == "capsule_hash":
        capsule["case_slots"][0]["fit_reason_mr"] = "Changed"
    else:
        if kind in ("pool_bytes", "overlay_bytes", "proof_bytes"):
            key = kind.split("_")[0]
            snapshot = capsule["snapshots"][key] if key != "proof" else capsule["snapshots"]["proofs"][0]
            snapshot["raw_json"] += " "
        elif kind == "selection_hash":
            capsule["selection"]["proposal_sha256"] = "0" * 64
        elif kind == "pair":
            capsule["selection"]["source_pair_ids"] = ["N9", "S9"]
        elif kind == "usage":
            capsule["used_case_ids"] = ["positive-e"]
        elif kind == "slot_extra":
            capsule["case_slots"][0]["text_mr"] = "Invented story"
        else:
            capsule["case_slots"][0]["fit_reason_mr" if kind == "fit_empty" else "limitations_mr"] = " "
        reseal(capsule)
    count = len(setup["fake"].calls)
    with pytest.raises(ValueError):
        compose(setup, capsule)
    assert len(setup["fake"].calls) == count


@pytest.mark.parametrize("defect", ["missing_proof", "partial_overlay", "invented_fact", "coverage_count",
                                    "identity_deleted", "original_record_changed"])
def test_complete_overlay_is_replayed_not_just_trusted_status_or_rehashed_snapshot(setup, defect):
    capsule = construct(setup)
    snapshot = capsule["snapshots"]["overlay"]
    document = json.loads(snapshot["raw_json"])
    if defect == "missing_proof":
        capsule["snapshots"]["proofs"].pop()
    elif defect == "partial_overlay":
        document["fact_verifications"].pop()
    elif defect == "invented_fact":
        document["fact_verifications"][1]["exact_supported_fact"] = "Invented replacement"
    elif defect == "coverage_count":
        document["coverage"]["pool_records"] = 2
    elif defect == "identity_deleted":
        document.pop("identity_verifications")
    else:
        document["proof_artifacts"][0]["document"]["fact_verifications"][0]["status"] = "QUALIFIED"
    replace_snapshot_document(snapshot, document)
    reseal(capsule)
    with pytest.raises((ValueError, KeyError)):
        compose(setup, capsule)


@pytest.mark.parametrize("defect", ["fact_hold", "identity_hold", "case_flag", "case_status",
                                    "global_identity", "used_case", "within_pair_relation", "used_case_relation",
                                    "same_identity", "unknown_used_case", "contradiction"])
def test_all_fact_and_identity_exclusions_hold_before_callbacks(setup, defect):
    options, overrides = {}, {}
    if defect == "fact_hold":
        options["statuses"] = {"caution-b": "HOLD"}
    elif defect == "identity_hold":
        options["identity_hold"] = "caution-b"
    elif defect == "case_flag":
        options["change"] = lambda pool: pool["cases"][1].update(flags=["HOLD_IDENTITY"])
    elif defect == "case_status":
        options["change"] = lambda pool: pool["cases"][1].update(new_book_status="HOLD_PENDING")
    elif defect == "global_identity":
        overrides["used_identity_keys"] = ["apple"]
    elif defect == "used_case":
        overrides["used_case_ids"] = {"positive-a"}
    elif defect == "within_pair_relation":
        options["relations"] = [("positive-a", "caution-b")]
    elif defect == "used_case_relation":
        options["relations"] = [("caution-b", "positive-e")]
        overrides["used_case_ids"] = {"positive-e"}
    elif defect == "same_identity":
        options["change"] = lambda pool: pool["cases"][1]["entity_identity"].update(
            recorded_aliases_and_related_labels=["Apple"])
    elif defect == "unknown_used_case":
        overrides["used_case_ids"] = {"unrecorded"}
    work = case_work(setup["tmp_path"] / "held-proofs", **options)
    if defect == "contradiction":
        path = work / "business-case-fresh-shard-1.json"
        shard = json.loads(path.read_text(encoding="utf-8"))
        shard["records"][0]["existing_marathi_material_fact_contradiction_found"] = True
        write_json(path, shard)
        write_json(work / OVERLAY, preparation.prepare_complete_case_overlay(work))
    count = len(setup["fake"].calls)
    with pytest.raises(ValueError):
        construct(setup, case_work_dir=work, **overrides)
    assert len(setup["fake"].calls) == count


@pytest.mark.parametrize("defect", ["one", "three", "reversed", "duplicate", "wrong_kind"])
def test_exactly_two_distinct_canonical_positive_caution_records(setup, defect):
    slots = construct(setup)["case_slots"]
    if defect == "one":
        slots.pop()
    elif defect == "three":
        slots.append(deepcopy(slots[0]))
    elif defect == "reversed":
        slots.reverse()
    elif defect == "duplicate":
        slots[1]["case_id"] = slots[0]["case_id"]
    else:
        slots[0]["case_id"] = "caution-d"
    with pytest.raises(ValueError):
        construct(setup, case_slots=slots)


def test_reject_and_original_source_hash_fail_before_capsule_is_even_read(setup):
    """An invalid capsule cannot bypass rejection or original source verification."""
    count = len(setup["fake"].calls)
    with pytest.raises(ValueError, match="Rejected source-first"):
        compose(setup, {"unread": True}, number=2, brief=setup["args"][1][1], sources=setup["args"][2]["2"])
    changed = deepcopy(setup["selection"]["sources"])
    changed["examples"] = [{"case_id": "injected-before-original-gate"}]
    with pytest.raises(ValueError, match="brief/sources changed"):
        compose(setup, {"unread": True}, sources=changed)
    assert len(setup["fake"].calls) == count


def test_full_and_selected_arbitration_have_identical_capsule_binding(setup):
    full = construct(setup)
    selected = deepcopy(setup["selection"])
    selected["proposal"] = selected["proposal"]["proposals"][0]
    selected["peer_review"] = {k: v["reviews"][0] for k, v in selected["peer_review"].items()}
    assert construct(setup, **selected) == full
    assert compose(setup, full, **selected)["status"] == "READY_FOR_AUTHOR_REVIEW"


@pytest.mark.parametrize("setup", VOICES[:-1], indirect=True)
@pytest.mark.parametrize("selected_only", [False, True])
def test_original_held_peer_rejects_fresh_build_apply_and_compose_without_callbacks(setup, selected_only, monkeypatch):
    """CAPSULE-01: an original, schema-valid HOLD fails even with consistent hashes."""
    from src.orchestration import source_first_case_capsule as capsule_module
    if selected_only:
        setup["selection"]["proposal"] = setup["selection"]["proposal"]["proposals"][0]
        setup["selection"]["peer_review"] = {
            role: value["reviews"][0] for role, value in setup["selection"]["peer_review"].items()}
    original_peers = setup["selection"]["peer_review"]
    selected_peers = {role: value["reviews"][0] if "reviews" in value else value
                      for role, value in original_peers.items()}
    assert sum(review["verdict"] == "REVIEW_REQUIRED" for review in selected_peers.values()) == 1
    # Reproduce the exact pre-fix artifact shape: create synthetic proof snapshots
    # using a separate all-PASS review copy, then bind every digest to the ACTUAL
    # originally held reviews. This is not a stale PASS-capsule/hash-drift test.
    pass_copy = deepcopy(original_peers)
    for value in pass_copy.values():
        review = value["reviews"][0] if "reviews" in value else value
        review.update(verdict="PASS", issues=[])
    capsule = construct(setup, peer_review=pass_copy)
    capsule["selection"]["peer_review_sha256"] = digest(selected_peers)
    capsule["selection"]["selection_sha256"] = digest({
        k: v for k, v in capsule["selection"].items() if k != "selection_sha256"})
    reseal(capsule)
    assert capsule["selection"]["peer_review_sha256"] == digest(selected_peers)
    def no_case_attachment(*args, **kwargs):
        """Tripwire: held selection must stop before even replaying case inventory."""
        pytest.fail("Held selection reached case inventory")
    monkeypatch.setattr(capsule_module, "_inventory", no_case_attachment)
    setup["fake"].calls.clear()
    with pytest.raises(ValueError, match="all three peer reviews PASS"):
        construct(setup)
    with pytest.raises(ValueError, match="all three peer reviews PASS"):
        apply_case_capsule(capsule, **setup["selection"], used_case_ids=set())
    with pytest.raises(ValueError, match="all three peer reviews PASS"):
        compose(setup, capsule)
    assert setup["fake"].calls == []


@pytest.mark.parametrize("selected_only", [False, True])
@pytest.mark.parametrize("defect", ["missing_role", "unknown_role", "malformed_peer", "wrong_number",
                                    "boolean_number", "missing_number", "unknown_verdict",
                                    "pass_with_issues", "missing_issues", "nonlist_issues"])
def test_capsule_build_and_compose_reject_malformed_peer_structure_without_callbacks(setup, selected_only, defect):
    """Exact peer coverage/types, integer identity and PASS/issues consistency fail closed."""
    capsule = construct(setup)
    if selected_only:
        setup["selection"]["proposal"] = setup["selection"]["proposal"]["proposals"][0]
        setup["selection"]["peer_review"] = {
            role: value["reviews"][0] for role, value in setup["selection"]["peer_review"].items()}
    peers = setup["selection"]["peer_review"]
    review = peers["narada"] if selected_only else peers["narada"]["reviews"][0]
    if defect == "missing_role":
        del peers["narada"]
    elif defect == "unknown_role":
        peers["unknown"] = peers.pop("narada")
    elif defect == "malformed_peer":
        peers["narada"] = None
    elif defect == "wrong_number":
        review["number"] = 99
    elif defect == "boolean_number":
        review["number"] = True
    elif defect == "missing_number":
        del review["number"]
    elif defect == "unknown_verdict":
        review["verdict"] = "APPROVED"
    elif defect == "pass_with_issues":
        review["issues"] = [{"field": "derivation", "quote": "Synthetic derivation",
                             "reason": "Unresolved fixture objection", "severity": "major"}]
    elif defect == "missing_issues":
        del review["issues"]
    else:
        review["issues"] = {}
    setup["fake"].calls.clear()
    with pytest.raises(ValueError):
        construct(setup)
    with pytest.raises(ValueError):
        compose(setup, capsule)
    assert setup["fake"].calls == []


@pytest.mark.parametrize("setup", ["narada"], indirect=True)
def test_no_capsule_preserves_original_peer_objection_composition_behavior(setup):
    """The stricter selection gate is capsule-only; original no-capsule inputs still work."""
    assert setup["selection"]["peer_review"]["narada"]["reviews"][0]["verdict"] == "REVIEW_REQUIRED"
    setup["fake"].calls.clear()
    result = compose(setup, None)
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW"
    assert len(setup["fake"].calls) == 3
    assert all("composition_binding" not in payload for payload in setup["fake"].calls)


def test_source_only_is_required_and_legacy_default_remains_strict(setup, tmp_path):
    capsule = construct(setup)
    fake = FakeCallbacks()
    legacy = fake.council(tmp_path / "legacy")
    args = batch_inputs((1,))
    batch = legacy.run_batch_discussion(*args)
    kwargs = dict(number=1, brief=args[1][0], sources=args[2]["1"], prior_formulas=args[3],
                  forbidden_originals=args[4], used_case_ids=set(), discussion=batch["discussion"],
                  proposal=batch["proposal"], peer_review=batch["peer_review"])
    with pytest.raises(ValueError, match="requires source-first"):
        legacy.compose_entry(**kwargs, case_capsule=capsule)
    changed = deepcopy(kwargs)
    changed["sources"]["examples"] = [{"case_id": "new"}]
    with pytest.raises(ValueError, match="brief/sources changed"):
        legacy.compose_entry(**changed)
    assert legacy.compose_entry(**kwargs)["status"] == "READY_FOR_AUTHOR_REVIEW"
    assert all("composition_binding" not in p for p in fake.calls)


def test_changed_fit_invalidates_only_composition_and_bound_provider_review_scope(setup):
    capsule = construct(setup)
    compose(setup, capsule)
    payload = next(p for p in setup["fake"].calls if p["stage"] == "composition")
    from src.orchestration.source_first_writing import writing_view
    view = bind_composition_view(writing_view(payload), payload)
    assert view["composition_binding"] == payload["composition_binding"]
    original_scope = composition_scope(payload)
    changed = deepcopy(capsule)
    changed["case_slots"][0]["limitations_mr"] += " Changed fit limitation."
    reseal(changed)
    sources, binding = apply_case_capsule(changed, **setup["selection"], used_case_ids=set())
    new_payload = {**payload, "sources": sources, "composition_binding": binding}
    assert composition_scope(new_payload) != original_scope
    assert binding["original_selection_sha256"] == payload["composition_binding"]["original_selection_sha256"]
    assert digest(bind_composition_view(writing_view(new_payload), new_payload)) != digest(view)
    count = len(setup["fake"].calls)
    with pytest.raises(ValueError, match="[Ii]nput"):
        compose(setup, changed)
    assert len(setup["fake"].calls) == count
    setup["instance"] = council(setup["tmp_path"] / "new-composition", setup["fake"])
    assert compose(setup, changed)["status"] == "READY_FOR_AUTHOR_REVIEW"
    assert Counter(p["stage"] for p in setup["fake"].calls)["position"] == 4


def test_raw_reviewer_prompt_unmodified_but_cache_namespaces_are_capsule_bound(setup):
    """The documented adapter scopes raw review caches without altering calibration."""
    from src.orchestration import independent_review as review
    from tests.test_independent_review_v2 import evidence, answer, source_check, reference_answer
    capsule = construct(setup)
    sources, binding = apply_case_capsule(capsule, **setup["selection"], used_case_ids=set())
    payload = {"sources": sources, "composition_binding": binding}
    calls = []
    draft, _, cards = evidence.__wrapped__()
    draft["references"] = deepcopy(sources["references"])
    draft["examples"] = deepcopy(sources["examples"])
    draft["case_ids"] = [c["case_id"] for c in sources["examples"]]
    draft["comparative_mr"] = [{"source_id": r["id"], "explanation_mr": "आधुनिक उपयोग."}
                               for r in sources["references"]]
    checks = [source_check(source_id=r["id"], source_quote=r["original_text"],
                            field=f"comparative_mr.{i}.explanation_mr")
              for i, r in enumerate(sources["references"])]
    def raw_call(system, prompt):
        calls.append((system, prompt))
        expected_payload = review.build_payload(draft, sources, cards)
        assert system == review.SYSTEM
        assert prompt == review.CONTRACT + "\nEVIDENCE\n" + json.dumps(
            expected_payload, ensure_ascii=False, sort_keys=True)
        return reference_answer(answer(source_checks=checks), expected_payload)
    reviewer = review.IndependentReviewer(setup["tmp_path"] / composition_scope(payload) / "review.db", raw_call)
    assert reviewer.path.parent.name == composition_scope(payload)
    first = reviewer.review(draft, sources, cards)
    assert first["verdict"] == "PASS" and len(calls) == 1
    assert reviewer.review(draft, sources, cards) == first and len(calls) == 1
    changed = deepcopy(capsule)
    changed["case_slots"][0]["limitations_mr"] += " Changed limit."
    reseal(changed)
    new_sources, new_binding = apply_case_capsule(changed, **setup["selection"], used_case_ids=set())
    new_payload = {"sources": new_sources, "composition_binding": new_binding}
    # Identical calibrated evidence still requires a fresh capsule-scoped review.
    next_reviewer = review.IndependentReviewer(
        setup["tmp_path"] / composition_scope(new_payload) / "review.db", raw_call)
    assert next_reviewer.review(draft, new_sources, cards)["verdict"] == "PASS"
    assert len(calls) == 2 and calls[0] == calls[1]
    with pytest.raises(ValueError, match="binding"):
        composition_scope({"sources": sources})
    with pytest.raises(ValueError, match="binding"):
        composition_scope({"sources": {}, "composition_binding": binding})
    assert bind_composition_view({"legacy": True}, {"sources": {}}) == {"legacy": True}


def test_current_draft_review_callback_receives_binding_without_old_proposal(setup):
    received = []
    def final_review(payload):
        received.append(deepcopy(payload))
        return {"outcome": "READY", "verdict": "PASS", "issues": []}
    setup["instance"] = ResearchCouncil(setup["tmp_path"] / "v2.db", setup["fake"].voices,
        setup["fake"].validator, setup["fake"].assessor, source_first_selection=True, final_review=final_review)
    capsule = construct(setup)
    result = compose(setup, capsule)
    assert result["status"] == "READY_FOR_AUTHOR_REVIEW" and len(received) == 1
    assert received[0]["composition_binding"]["case_capsule_sha256"] == capsule["capsule_sha256"]
    assert received[0]["discussion"] == {} and "proposal" not in received[0]


def test_fake_budgeted_provider_reuses_exact_capsule_and_rejects_changed_binding(setup, monkeypatch):
    """The actual durable provider boundary retains both digests after a lean view."""
    from scripts import run_research_book as runner
    from src.orchestration.source_first_provider import SourceFirstProvider
    from src.orchestration.source_first_writing import writing_view
    from tests.test_source_first_provider import FakeRegistry
    def forbidden(*args, **kwargs):
        pytest.fail("Credential/SDK construction forbidden")
    monkeypatch.setattr(runner, "load_project_credentials", forbidden)
    monkeypatch.setattr("src.providers.registry.ProviderRegistry", forbidden)
    capsule = construct(setup)
    compose(setup, capsule)
    payload = next(p for p in setup["fake"].calls if p["stage"] == "composition")
    view = bind_composition_view(writing_view(payload), payload)
    registry = FakeRegistry()
    root = setup["tmp_path"] / composition_scope(payload) / "provider"
    def client(binding, resume=False):
        """Open the fake boundary with explicit fresh/resume semantics."""
        return SourceFirstProvider(root, registry, source_hashes=binding,
                                   max_usd=1, max_calls=10, claude_cap_usd=.5, resume=resume)
    provider = client(payload["composition_binding"])
    result = provider("sutrakar", "entry-001/composition", "Synthetic JSON only.", view, 100)
    adapter = registry.adapters[runner.MODELS["sutrakar"][0]]
    assert adapter.calls == 1
    for key in ("original_selection_sha256", "case_capsule_sha256"):
        assert payload["composition_binding"][key] in adapter.observed[0][0]
    resumed = client(payload["composition_binding"], resume=True)
    assert resumed("sutrakar", "entry-001/composition", "Synthetic JSON only.", view, 100) == result
    assert adapter.calls == 1
    changed = deepcopy(payload["composition_binding"])
    changed["case_capsule_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        client(changed, resume=True)
    assert adapter.calls == 1


def test_imports_do_not_load_provider_sdks_or_credentials():
    """An isolated import fails immediately if any SDK/credential module is touched."""
    script = """
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'openai', 'anthropic', 'google', 'dotenv'} or 'credential' in name:
        raise AssertionError('Forbidden import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import src.orchestration.source_first_case_capsule
import src.orchestration.research_council
"""
    result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parents[1], timeout=20)
    assert result.returncode == 0, result.stderr

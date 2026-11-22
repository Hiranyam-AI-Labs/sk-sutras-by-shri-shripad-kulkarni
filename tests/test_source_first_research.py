"""Offline selection boundaries with synthetic records; no models, keys or I/O."""

import hashlib
from copy import deepcopy

import pytest

from src.orchestration.source_first_research import (
    prepare_research_batch, run_source_first_research, validate_research_selection,
)


def digest(text):
    """Return the exact UTF-8 digest of a fixture passage, without normalization."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def packet():
    """Supply two distinct pairs and parent-checked, pair-scoped passage records."""
    hashes = {"narada": "a" * 64, "shandilya": "b" * 64, "external": "c" * 64}
    candidates, evidence = [], []
    for number in (1, 2):
        candidates.append({
            "id": f"pair-{number}",
            "narada": {"id": number, "sanskrit": "अथातो भक्तिं व्याख्यास्यामः ॥",
                       "meaning_mr": "प्रेमाविषयी विचार करण्याचा येथे आरंभ आहे",
                       "context_mr": "उदाहरणासाठी दिलेली स्वतंत्र कार्यप्रत आहे"},
            "shandilya": {"id": number, "sanskrit": "सा परानुरक्तिरीश्वरे ॥",
                          "meaning_mr": "ईश्वराविषयी उत्कट प्रेमाचे येथे वर्णन आहे",
                          "context_mr": "ही स्वतंत्र व्याख्या उदाहरणासाठी दिली आहे"},
            "source_hashes": {k: hashes[k] for k in ("narada", "shandilya")},
            "scores": {"meaning": 30, "proposition": 12.5, "context": 10, "conditions": 7.5},
            "total": 60, "blockers": [], "failed_primary_minima": [],
            "qualifications": ["Synthetic fixture, no source certification"],
        })
        passage = f"Canonical fixture {number}: distinct wording.\nअचूक पुरवलेला उतारा ॥"
        evidence.append({"id": f"evidence-{number}", "candidate_id": f"pair-{number}",
                         "source_id": "external", "source_sha256": hashes["external"],
                         "location": f"paragraph:{number}", "canonical_passage": passage,
                         "passage_sha256": digest(passage), "verified": True, "eligible": True})
    return candidates, evidence, hashes


def prepare(packet):
    """Prepare the fixture using a stable batch identity; no hidden paths."""
    return prepare_research_batch("batch-1", *packet)


def response(request, status="SUPPORTED"):
    """Return explicit prose layers, allowing distinct claims rather than identity."""
    return {"batch_id": request["batch_id"], "request_sha256": request["request_sha256"],
            "source_hashes": deepcopy(request["source_hashes"]), "assessments": [{
                "candidate_id": candidate["id"], "status": status,
                "evidence_ids": candidate["eligible_evidence_ids"][:1] if status == "SUPPORTED" else [],
                "relation_kind": "DISTINCT" if status != "PENDING" else "UNRESOLVED",
                "source_core_mr": {
                    "narada_mr": "नारदांच्या विधानात प्रेमाचा विचार सुरू करण्याचा विशिष्ट निर्देश येथे दिला आहे",
                    "shandilya_mr": "शाण्डिल्यांच्या व्याख्येमध्ये ईश्वरावरील उत्कट प्रेमाचे स्वतंत्र स्वरूप येथे स्पष्ट केले आहे",
                },
                "relation_mr": "दोन्ही विधानांचे विषय संबंधित आहेत परंतु आरंभ आणि व्याख्या यांची कार्ये भिन्न आहेत",
                "limitations_mr": "या तुलनेत संपूर्ण तत्त्वज्ञानाची समानता किंवा विद्वानांची मान्यता गृहीत धरता येत नाही",
                "business_extension_mr": "व्यवसायातील निर्णयासाठी उद्दिष्ट आधी स्पष्ट करणे हा स्वतंत्र आधुनिक उपयोग सुचवता येतो",
            } for candidate in request["candidates"]]}


# Verify concise notes for excluded candidates do not cause artificial padding
# or another model call. The exception is explicit and never promotes a pair.
def test_concise_nonadvancing_decline_note_is_recorded(packet):
    request = prepare_research_batch('decline', *packet)
    answer = response(request)
    for row in answer['assessments']:
        row['status'] = 'UNSUPPORTED'
        row['evidence_ids'] = []
        row['business_extension_mr'] = 'आधार नसल्याने व्यवसायविस्तार सुचवलेला नाही'
    result = validate_research_selection(request, answer)
    assert result['summary']['SUPPORTED'] == 0
    assert result['summary']['UNSUPPORTED'] == 2
    assert len(result['non_advancing_decline_note_exceptions']) == 2
    assert all(not row['selected_evidence'] for row in result['assessments'])


# Verify accepted candidates cannot use the shorter exclusion-note allowance.
def test_supported_candidate_keeps_original_substantive_extension_floor(packet):
    request = prepare_research_batch('supported-floor', *packet)
    answer = response(request)
    answer['assessments'][0]['business_extension_mr'] = 'आधार नसल्याने व्यवसायविस्तार सुचवलेला नाही'
    with pytest.raises(ValueError, match='8 words'):
        validate_research_selection(request, answer)


def test_callback_once_exact_passages_summary_and_no_mutation(packet):
    """Reordered decisions preserve coverage, input order and literal canonical bytes."""
    before, calls = deepcopy(packet), []

    def researcher(request):
        """Emulate a parsed model result, with a deliberately different row order."""
        calls.append(deepcopy(request))
        answer = response(request)
        answer["assessments"].reverse()
        return answer

    result = run_source_first_research("batch-1", *packet, researcher)
    assert len(calls) == 1 and packet == before
    assert result["summary"] == {"pairs": 2, "SUPPORTED": 2, "UNSUPPORTED": 0,
                                 "PENDING": 0, "selected_evidence": 2}
    assert [r["candidate_id"] for r in result["assessments"]] == ["pair-1", "pair-2"]
    assert result["assessments"][0]["selected_evidence"] == [packet[1][0]]
    assert result["assessments"][0]["relation_kind"] == "DISTINCT"
    assert "not semantic/source verification" in result["acceptance_scope"]
    assert "verified" not in result and "scholar_verified" not in result
    result["assessments"][0]["selected_evidence"][0]["canonical_passage"] = "changed output"
    assert packet == before


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "foreign", "wrong_type"])
def test_exact_batch_coverage(packet, change):
    """Missing, repeated and foreign decisions cannot masquerade as full coverage."""
    request = prepare(packet)
    answer = response(request)
    rows = answer["assessments"]
    if change == "missing":
        rows.pop()
    elif change == "extra":
        rows.append(deepcopy(rows[0]))
    elif change == "duplicate":
        rows[1] = deepcopy(rows[0])
    elif change == "foreign":
        rows[1]["candidate_id"] = "not-supplied"
    else:
        rows[1]["candidate_id"] = []
    with pytest.raises(ValueError, match="coverage"):
        validate_research_selection(request, answer)


@pytest.mark.parametrize("ids,message", [
    ([], "requires resolved"), (["invented"], "unknown evidence"),
    (["evidence-2"], "another pair"), (["evidence-1", "evidence-1"], "unique"),
    ([{}], "unique"), ("evidence-1", "unique"),
])
def test_malformed_or_unowned_evidence_selection(packet, ids, message):
    """Only actual, uniquely chosen, pair-owned evidence may support a decision."""
    request = prepare(packet)
    answer = response(request)
    answer["assessments"][0]["evidence_ids"] = ids
    with pytest.raises(ValueError, match=message):
        validate_research_selection(request, answer)


@pytest.mark.parametrize("flag", ["eligible", "verified"])
def test_unverified_or_ineligible_evidence_cannot_support(packet, flag):
    """Callback cannot promote parent-disallowed evidence by choosing its known ID."""
    packet[1][0][flag] = False
    request = prepare(packet)
    answer = response(request)
    answer["assessments"][0]["evidence_ids"] = ["evidence-1"]
    with pytest.raises(ValueError, match="ineligible, unverified"):
        validate_research_selection(request, answer)


@pytest.mark.parametrize("failure", ["blocker", "declared_minimum", "computed_minimum", "reserve"])
def test_pair_eligibility_cannot_be_overridden(packet, failure):
    """Even total >=60 cannot rescue failed minima, and reserves are not promoted."""
    candidate = packet[0][0]
    if failure == "blocker":
        candidate["blockers"] = ["material_unresolved_meaning"]
    elif failure == "declared_minimum":
        candidate["failed_primary_minima"] = ["independent policy restriction"]
    elif failure == "computed_minimum":
        candidate["scores"].update(meaning=29, proposition=20)
        candidate["total"] = 66.5
    else:
        candidate["scores"]["conditions"] = 7
        candidate["total"] = 59.5
    request = prepare(packet)
    answer = response(request)
    answer["assessments"][0]["evidence_ids"] = ["evidence-1"]
    with pytest.raises(ValueError, match="blocked or failed primary"):
        validate_research_selection(request, answer)
    answer["assessments"][0].update(status="UNSUPPORTED", evidence_ids=[])
    assert validate_research_selection(request, answer)["summary"]["UNSUPPORTED"] == 1


def test_unsupported_and_pending_preserve_no_match_without_forced_identity(packet):
    """A fully covered no-match batch is valid, without evidence invention or retry."""
    packet[0][0]["blockers"] = ["unresolved"]
    packet[1].clear()
    request = prepare(packet)
    answer = response(request, "UNSUPPORTED")
    answer["assessments"][1].update(status="PENDING", relation_kind="UNRESOLVED")
    result = validate_research_selection(request, answer)
    assert result["summary"] == {"pairs": 2, "SUPPORTED": 0, "UNSUPPORTED": 1,
                                 "PENDING": 1, "selected_evidence": 0}
    assert all(not row["selected_evidence"] for row in result["assessments"])
    answer["assessments"][0]["evidence_ids"] = ["invented"]
    with pytest.raises(ValueError, match="cannot select"):
        validate_research_selection(request, answer)


@pytest.mark.parametrize("where,field", [
    ("row", "quote"), ("row", "canonical_passage"), ("row", "verified"),
    ("root", "quotations"), ("root", "scholar_verified"), ("core", "generated_quote"),
])
def test_generated_quote_and_verification_claim_fields_rejected(packet, where, field):
    """Allowlisted responses cannot supply replacement passages or certification flags."""
    request = prepare(packet)
    answer = response(request)
    target = answer if where == "root" else answer["assessments"][0]
    if where == "core":
        target = target["source_core_mr"]
    target[field] = "invented"
    with pytest.raises(ValueError):
        validate_research_selection(request, answer)


@pytest.mark.parametrize("field,value", [
    ("status", "PASS"), ("status", []), ("relation_kind", "IDENTICAL_BY_DEFAULT"),
    ("relation_kind", "UNRESOLVED"), ("source_core_mr", "merged sources"),
    ("limitations_mr", "मर्यादा नाहीत"), ("relation_mr", "English words cannot pad this rationale at all"),
    ("business_extension_mr", "व्यवसाय " * 12),
])
def test_required_status_and_substantive_separate_marathi(packet, field, value):
    """Bad statuses, merged cores and token padding fail rather than imply support."""
    request = prepare(packet)
    answer = response(request)
    answer["assessments"][0][field] = value
    with pytest.raises(ValueError):
        validate_research_selection(request, answer)


def test_reusing_source_claim_as_business_extension_rejected(packet):
    """The same boilerplate cannot fill distinct source and modern-application layers."""
    request = prepare(packet)
    answer = response(request)
    row = answer["assessments"][0]
    row["business_extension_mr"] = row["source_core_mr"]["narada_mr"]
    with pytest.raises(ValueError, match="separate prose"):
        validate_research_selection(request, answer)


@pytest.mark.parametrize("fault", ["candidate_hash", "evidence_hash", "passage", "duplicate_pair",
                                  "duplicate_candidate", "duplicate_evidence", "foreign_source",
                                  "foreign_owner", "wrong_flag", "bad_score", "boolean_score", "bad_total"])
def test_invalid_input_rejected_before_callback(packet, fault):
    """Source drift and malformed eligibility are rejected without spending a callback."""
    candidates, evidence, hashes = packet
    if fault == "candidate_hash":
        candidates[0]["source_hashes"]["narada"] = "d" * 64
    elif fault == "evidence_hash":
        evidence[0]["source_sha256"] = "d" * 64
    elif fault == "passage":
        evidence[0]["canonical_passage"] += " "
    elif fault == "duplicate_pair":
        candidates[1]["narada"]["id"] = candidates[1]["shandilya"]["id"] = 1
    elif fault == "duplicate_candidate":
        candidates[1]["id"] = candidates[0]["id"]
    elif fault == "duplicate_evidence":
        evidence[1]["id"] = evidence[0]["id"]
    elif fault == "foreign_source":
        evidence[0]["source_id"] = "unregistered"
    elif fault == "foreign_owner":
        evidence[0]["candidate_id"] = "foreign"
    elif fault == "wrong_flag":
        evidence[0]["verified"] = "true"
    elif fault == "bad_score":
        candidates[0]["scores"]["meaning"] = 30.1
    elif fault == "boolean_score":
        candidates[0]["scores"]["meaning"] = True
    else:
        candidates[0]["total"] = 99
    calls = []
    with pytest.raises(ValueError):
        run_source_first_research("batch-1", candidates, evidence, hashes, calls.append)
    assert not calls


@pytest.mark.parametrize("key", ["batch_id", "request_sha256", "source_hashes"])
def test_response_echo_cannot_drift(packet, key):
    """Stale responses and a changed trusted hash registry never bind a new batch."""
    request = prepare(packet)
    answer = response(request)
    answer[key] = {} if key == "source_hashes" else "stale"
    with pytest.raises(ValueError, match="drift"):
        validate_research_selection(request, answer)


def test_request_tampering_and_callback_mutation_are_detected(packet):
    """Changing passage and its digest still invalidates the original whole-packet binding."""
    request = prepare(packet)
    answer = response(request)
    request["evidence_records"][0]["canonical_passage"] += "changed"
    request["evidence_records"][0]["passage_sha256"] = digest(request["evidence_records"][0]["canonical_passage"])
    with pytest.raises(ValueError, match="binding"):
        validate_research_selection(request, answer)
    before = deepcopy(packet)

    def mutating_callback(copy):
        """Tamper with the isolated working copy and attempt to use its changed digest."""
        copy["request_sha256"] = "forged"
        copy["evidence_records"][0]["canonical_passage"] = "invented"
        return response(copy)

    with pytest.raises(ValueError, match="request_sha256 drift"):
        run_source_first_research("batch-1", *packet, mutating_callback)
    assert packet == before


def test_callback_failure_propagates_without_retry(packet):
    """The parent, not this offline gate, owns retry/call-budget policy."""
    calls = []

    def fail(request):
        """Count exactly one attempt before raising a synthetic callback error."""
        calls.append(request)
        raise RuntimeError("synthetic callback failure")

    with pytest.raises(RuntimeError, match="synthetic"):
        run_source_first_research("batch-1", *packet, fail)
    assert len(calls) == 1


def test_bounded_empty_and_oversized_batches(packet):
    """Empty and oversized inputs fail before any model dispatch or persistence."""
    candidates, evidence, hashes = packet
    for rows in ([], candidates * 51):
        with pytest.raises(ValueError, match="1..100"):
            prepare_research_batch("bounded", rows, evidence, hashes)
    with pytest.raises(ValueError, match="1000"):
        prepare_research_batch("bounded", candidates, evidence * 501, hashes)

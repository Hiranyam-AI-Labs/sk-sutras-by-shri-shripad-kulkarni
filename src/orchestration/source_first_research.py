"""Offline evidence-selection gate; model/provider wiring belongs to the parent.

API usage contract
------------------
``prepare_research_batch(batch_id, candidates, evidence_records, source_hashes)``
accepts plain JSON dictionaries, with no paths or checkpoint dependencies:

* Each candidate has a unique ``id``, ``narada`` and ``shandilya`` records (each
  with positive integer ``id``, ``sanskrit``, ``meaning_mr``, ``context_mr``),
  ``source_hashes`` matching the registered narada/shandilya hashes, four
  ``scores`` (meaning/proposition/context/conditions), ``total``, ``blockers``
  and ``failed_primary_minima`` lists. Extra JSON context is preserved.
* Each evidence record has unique ``id``, owning ``candidate_id``, registered
  ``source_id``, ``source_sha256``, ``location``, ``canonical_passage``, its
  exact UTF-8 ``passage_sha256``, and boolean ``eligible``/``verified`` flags.
  The parent supplies independently checked canonical records and trusted
  current source hashes; this gate cannot verify a file or external source.
* The request contains derived selection eligibility and evidence ID menus.
  At most 100 distinct 1-Narada/1-Shandilya pairs and 1000 evidence records
  may enter a batch. Primary minima are 30/12.5/10/7.5 and total >=60;
  declarations cannot bypass computed failed minima or blockers.

``run_source_first_research(..., researcher)`` calls the synchronous callback
exactly once with an isolated request copy. No retries, provider imports, usage
accounting, persistence or network calls occur here. The parent owns model
calls, budget enforcement, JSON parsing, usage metadata and work paths. It may
instead call prepare and ``validate_research_selection(request, response)``.

Callback response has EXACT keys ``batch_id``, ``request_sha256``,
``source_hashes`` (echo the full registry), and ``assessments``. Every supplied
candidate appears exactly once, with EXACT keys ``candidate_id``, ``status``
(SUPPORTED/UNSUPPORTED/PENDING), ``evidence_ids``, ``relation_kind``
(PARTIAL_OVERLAP/COMPLEMENTARY/DISTINCT/TENSION/UNRESOLVED), ``source_core_mr``
({narada_mr, shandilya_mr}), ``relation_mr``, ``limitations_mr`` and
``business_extension_mr``. Prose fields require at least eight Devanagari words
and four distinct such words; this is a cheap script/substance floor, NOT
Marathi language detection or semantic verification. Explain actual source
propositions, their interaction, limits, and a separately labelled business
extension. Never force identity, present that extension as a source teaching,
or claim this gate/model independently verified quotations or scholarship.

For non-advancing UNSUPPORTED/PENDING results only, the business-extension field
may be a concise Marathi decline note (three words, two distinct). This explicit
post-validation exception is recorded per pair; historical request contracts
remain unchanged. Supported cases and all source/relation/limitation fields keep
their original substantive floor. A decline cannot select evidence or advance.

SUPPORTED requires an eligible pair, a resolved relation, and >=1 supplied,
eligible, externally verified evidence ID owned by that pair. Other statuses
select no evidence. Unknown/extra response fields (including regenerated quote
fields) fail closed. Output attaches canonical records ONLY from the request,
ordered by input candidates, plus status counts. PASS means contract/binding
acceptance, not semantic truth, publication approval or completion of PENDING
work. No quotation is accepted from callback prose as canonical evidence.
"""

import hashlib
import json
import math
import re
from copy import deepcopy
from typing import Callable

from src.orchestration.research_acceptance import _devanagari_word


COMPONENTS = {"meaning": (40, 30), "proposition": (25, 12.5),
              "context": (20, 10), "conditions": (15, 7.5)}
STATUSES = ("SUPPORTED", "UNSUPPORTED", "PENDING")
RELATIONS = ("PARTIAL_OVERLAP", "COMPLEMENTARY", "DISTINCT", "TENSION", "UNRESOLVED")
PROSE_FIELDS = ("relation_mr", "limitations_mr", "business_extension_mr")
ASSESSMENT_FIELDS = {"candidate_id", "status", "evidence_ids", "relation_kind",
                     "source_core_mr", *PROSE_FIELDS}


def _require(condition: bool, message: str) -> None:
    """Raise ValueError for a failed untrusted contract condition; never coerce."""
    if not condition:
        raise ValueError(message)


def _text(value: object) -> bool:
    """Return whether a field is a nonblank string; preserve original bytes."""
    return isinstance(value, str) and bool(value.strip())


def _digest(value: object) -> str:
    """Hash deterministic JSON; reject non-JSON and nonfinite values before use."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _hashes(value: object) -> bool:
    """Check a nonempty registry of source IDs and lowercase SHA256 strings."""
    return (isinstance(value, dict) and bool(value)
            and all(_text(k) and isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)
                    for k, v in value.items()))


def _strings(value: object) -> bool:
    """Require an explicit list of nonblank diagnostic/identity strings."""
    return isinstance(value, list) and all(_text(item) for item in value)


def _candidate_reasons(candidate: dict, hashes: dict) -> list[str]:
    """Validate one pair; return derived eligibility failures without scoring it."""
    _require(isinstance(candidate, dict) and _text(candidate.get("id")),
             "candidate requires a nonblank id")
    for source in ("narada", "shandilya"):
        record = candidate.get(source)
        _require(isinstance(record, dict) and type(record.get("id")) is int
                 and record["id"] > 0
                 and all(_text(record.get(k)) for k in
                         ("sanskrit", "meaning_mr", "context_mr")),
                 f"candidate {source} requires exactly one complete source record")
    _require(candidate.get("source_hashes") == {k: hashes[k] for k in ("narada", "shandilya")},
             "candidate source hash drift")
    for field in ("blockers", "failed_primary_minima"):
        _require(_strings(candidate.get(field)), f"candidate requires {field} list")
    scores = candidate.get("scores")
    _require(isinstance(scores, dict) and set(scores) == set(COMPONENTS),
             "candidate requires four component scores")
    for key, (maximum, _) in COMPONENTS.items():
        score = scores[key]
        _require(type(score) in (int, float) and 0 <= score <= maximum
                 and math.isfinite(score) and score * 2 % 1 == 0,
                 f"invalid component score: {key}")
    total = candidate.get("total")
    _require(type(total) in (int, float) and total == sum(scores.values())
             and math.isfinite(total), "invalid candidate total")
    reasons = list(candidate["blockers"]) + list(candidate["failed_primary_minima"])
    reasons.extend(f"failed primary minimum: {key}" for key, (_, minimum) in COMPONENTS.items()
                   if scores[key] < minimum)
    if total < 60:
        reasons.append("below primary total")
    return reasons


def prepare_research_batch(batch_id: str, candidates: list[dict],
                           evidence_records: list[dict], source_hashes: dict) -> dict:
    """Purpose: freeze a bounded plain-record request and derived ID menus.

    Parameters follow the module API contract. Returns an isolated request with
    a deterministic SHA256 binding the whole packet. ValueError rejects malformed
    records, duplicate pairs/IDs, or source/passage hash drift; TypeError rejects
    non-JSON input. Inputs stay untouched; no evidence is retrieved or certified.
    """
    _digest([batch_id, candidates, evidence_records, source_hashes])
    _require(_text(batch_id), "batch_id must be nonblank")
    _require(_hashes(source_hashes) and {"narada", "shandilya"} <= set(source_hashes),
             "source_hashes requires registered narada/shandilya SHA256 values")
    _require(isinstance(candidates, list) and 1 <= len(candidates) <= 100,
             "batch requires 1..100 candidates")
    _require(isinstance(evidence_records, list) and len(evidence_records) <= 1000,
             "batch requires at most 1000 evidence records")
    indexed, pairs = {}, set()
    for candidate in candidates:
        reasons = _candidate_reasons(candidate, source_hashes)
        identifier = candidate["id"]
        pair = (candidate["narada"]["id"], candidate["shandilya"]["id"])
        _require(identifier not in indexed and pair not in pairs, "duplicate candidate ID or pair")
        pairs.add(pair)
        indexed[identifier] = {**deepcopy(candidate), "selection_eligible": not reasons,
                               "selection_blockers": reasons, "eligible_evidence_ids": []}
    seen = set()
    for record in evidence_records:
        _require(isinstance(record, dict) and _text(record.get("id")), "evidence requires id")
        identifier = record["id"]
        _require(identifier not in seen, "duplicate evidence ID")
        seen.add(identifier)
        owner, source = record.get("candidate_id"), record.get("source_id")
        _require(_text(owner) and owner in indexed, "unknown evidence candidate_id")
        _require(_text(source) and source in source_hashes, "unknown evidence source_id")
        _require(record.get("source_sha256") == source_hashes[source], "evidence source hash drift")
        _require(_text(record.get("location")) and _text(record.get("canonical_passage")),
                 "evidence requires location and canonical_passage")
        passage_hash = hashlib.sha256(record["canonical_passage"].encode("utf-8")).hexdigest()
        _require(record.get("passage_sha256") == passage_hash, "canonical passage hash drift")
        _require(all(type(record.get(k)) is bool for k in ("verified", "eligible")),
                 "evidence requires boolean verified/eligible flags")
        if record["verified"] and record["eligible"] and indexed[owner]["selection_eligible"]:
            indexed[owner]["eligible_evidence_ids"].append(identifier)
    request = {"schema_version": 1, "batch_id": batch_id, "source_hashes": deepcopy(source_hashes),
               "selection_contract": {
                   "statuses": list(STATUSES), "relation_kinds": list(RELATIONS),
                   "assessment_fields": sorted(ASSESSMENT_FIELDS),
                   "source_core_fields": ["narada_mr", "shandilya_mr"],
                   "minimum_devanagari_words_per_field": 8,
                   "minimum_distinct_devanagari_words_per_field": 4,
                   "instructions": (
                       "Assess every supplied pair exactly once. Select only eligible evidence IDs; "
                       "never generate quote fields. Explain each source core separately, the actual "
                       "relation and its conditions, limitations, then a separate modern business "
                       "extension. Do not force identity or claim source/scholarly verification. "
                       "SUPPORTED needs a resolved relation and selected evidence; UNSUPPORTED/PENDING "
                       "select no evidence. Echo batch_id, request_sha256 and source_hashes."
                   ),
               },
               "candidates": list(indexed.values()), "evidence_records": deepcopy(evidence_records)}
    request["request_sha256"] = _digest(request)
    return request


def _marathi(value: object, field: str) -> None:
    """Enforce a script/length/diversity floor; do not certify Marathi semantics."""
    _require(_text(value), f"{field} requires substantive Marathi prose")
    words = [word for word in value.split() if _devanagari_word(word)]
    _require(len(words) >= 8 and len(set(words)) >= 4,
             f"{field} requires substantive Marathi prose (8 words, 4 distinct)")


def validate_research_selection(request: dict, response: dict) -> dict:
    """Purpose: require exact decisions and rehydrate only bound canonical evidence.

    Parameters: prepared request and parsed callback response from the module
    contract. Returns PASS, canonical assessments and counts (including pending).
    ValueError rejects missing/foreign/duplicate IDs, forbidden quote/claim fields,
    stale bindings or unsupported promotion. It checks structural consistency,
    not whether a relationship is semantically true; inputs remain unchanged.
    """
    _require(isinstance(request, dict), "request must be a prepared dictionary")
    expected = prepare_research_batch(request.get("batch_id"), request.get("candidates"),
                                      request.get("evidence_records"), request.get("source_hashes"))
    _require(request == expected, "prepared request binding or eligibility drift")
    _require(isinstance(response, dict) and set(response) ==
             {"batch_id", "request_sha256", "source_hashes", "assessments"},
             "response fields must be selection-only; no generated quotes or verification claims")
    for key in ("batch_id", "request_sha256", "source_hashes"):
        _require(response[key] == request[key], f"response {key} drift")
    rows = response["assessments"]
    _require(isinstance(rows, list) and len(rows) == len(request["candidates"]),
             "exact batch coverage required")
    candidates = {row["id"]: row for row in request["candidates"]}
    evidence = {row["id"]: row for row in request["evidence_records"]}
    decisions, decline_exceptions = {}, []
    for row in rows:
        _require(isinstance(row, dict) and set(row) == ASSESSMENT_FIELDS,
                 "assessment fields must be selection-only; no generated quotes or verification claims")
        identifier = row["candidate_id"]
        _require(_text(identifier) and identifier in candidates and identifier not in decisions,
                 "unknown or duplicate candidate_id; exact batch coverage required")
        status, relation = row["status"], row["relation_kind"]
        _require(isinstance(status, str) and status in STATUSES, "unknown assessment status")
        _require(isinstance(relation, str) and relation in RELATIONS, "unknown relation_kind")
        core = row["source_core_mr"]
        _require(isinstance(core, dict) and set(core) == {"narada_mr", "shandilya_mr"},
                 "source_core_mr must separate narada_mr and shandilya_mr")
        for key in core:
            _marathi(core[key], key)
        for key in PROSE_FIELDS:
            if key == 'business_extension_mr' and status != 'SUPPORTED':
                value = row[key]
                _require(_text(value), 'Non-advancing decline note must be explicit')
                words = [word for word in value.split() if _devanagari_word(word)]
                _require(len(words) >= 3 and len(set(words)) >= 2,
                         'Non-advancing decline note requires clear Marathi prose')
                if len(words) < 8 or len(set(words)) < 4:
                    decline_exceptions.append({'candidate_id': identifier,
                        'field': key, 'policy': 'non-advancing-decline-note-v1',
                        'devanagari_words': len(words),
                        'scope': 'Concise exclusion only; no evidence selection or candidate promotion'})
            else:
                _marathi(row[key], key)
        texts = [*core.values(), *(row[k] for k in PROSE_FIELDS)]
        _require(len({" ".join(t.split()) for t in texts}) == len(texts),
                 "source core, relation, limitations and business extension must be separate prose")
        ids = row["evidence_ids"]
        _require(_strings(ids) and len(set(ids)) == len(ids), "evidence_ids must be unique ID strings")
        if status == "SUPPORTED":
            candidate = candidates[identifier]
            _require(candidate["selection_eligible"], "blocked or failed primary minima candidate")
            _require(relation != "UNRESOLVED" and bool(ids), "SUPPORTED requires resolved relation and evidence")
            _require(all(i in evidence for i in ids), "unknown evidence ID")
            _require(all(i in candidate["eligible_evidence_ids"] for i in ids),
                     "evidence ID is ineligible, unverified or belongs to another pair")
        else:
            _require(not ids, "UNSUPPORTED/PENDING cannot select evidence")
        decisions[identifier] = {**deepcopy(row), "selected_evidence": [deepcopy(evidence[i]) for i in ids]}
    counts = {status: sum(row["status"] == status for row in decisions.values()) for status in STATUSES}
    result = {"status": "PASS", "batch_id": request["batch_id"],
            "request_sha256": request["request_sha256"], "source_hashes": deepcopy(request["source_hashes"]),
            "assessments": [decisions[row["id"]] for row in request["candidates"]],
            "summary": {"pairs": len(decisions), **counts,
                        "selected_evidence": sum(len(row["evidence_ids"]) for row in decisions.values())},
            "acceptance_scope": "Contract and canonical bindings only; not semantic/source verification or publication approval"}
    if decline_exceptions:
        result['non_advancing_decline_note_exceptions'] = decline_exceptions
    return result


def run_source_first_research(batch_id: str, candidates: list[dict], evidence_records: list[dict],
                               source_hashes: dict, researcher: Callable[[dict], dict]) -> dict:
    """Prepare, call once and validate; parent owns APIs, budgets and durable paths.

    Returns the validated summary and canonical selections. Callback exceptions
    propagate without retry; callback mutation cannot alter the frozen request
    or caller records. Invalid inputs fail before the callback is invoked.
    """
    request = prepare_research_batch(batch_id, candidates, evidence_records, source_hashes)
    return validate_research_selection(request, researcher(deepcopy(request)))

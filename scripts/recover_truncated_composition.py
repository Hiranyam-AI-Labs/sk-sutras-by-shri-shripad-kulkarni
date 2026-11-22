"""Explicit one-call continuation of a diagnosed composition prefix; no SDK calls.

The parent supplies a budgeted Sonnet callback. Existing failed attempts and raw
files remain intact; a recovered composition still needs independent review.
"""

import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path

from scripts.run_research_book import SYSTEM, complete_entry, planned_batches
from scripts.run_book_council_v19 import parse_object
from src.orchestration.independent_review import canonical_hash
from src.orchestration.research_acceptance import assess_research_entry
from src.orchestration.research_council import ResearchCouncil, PROTOCOL_VERSION, _check_answer, _json

PRESERVED = ("title_mr", "new_sutra", "grammar_mr", "translation_mr", "exposition", "references")
MISSING = ("comparative_mr", "case_ids", "dos_mr", "donts_mr", "application_mr", "action_mr", "summary_mr")
TABLE = "research_composition_continuations"
ERROR = "RuntimeError: Provider response truncated; partial text saved, no automatic retry"


def digest(value):
    """Hash canonical council JSON, matching original checkpoint request hashes."""
    return hashlib.sha256(_json(value).encode()).hexdigest()


def complete_prefix(text):
    """Parse six fields before a partial comparison key, or ten before a partial string.

    Return their decoded values without changing strings. Other boundaries,
    duplicate keys, complete objects or malformed JSON raise; no text is repaired.
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].lstrip()
    if not text.startswith("{"):
        raise ValueError("Partial composition must begin with a JSON object")
    decoder, fields, tail = json.JSONDecoder(), {}, text[1:].lstrip()
    for expected in PRESERVED + MISSING[:4]:
        key, end = decoder.raw_decode(tail)
        if key != expected:
            raise ValueError("Unexpected completed prefix field")
        tail = tail[end:].lstrip()
        if not tail.startswith(":"):
            raise ValueError("Missing field separator")
        value, end = decoder.raw_decode(tail[1:].lstrip())
        fields[key] = value
        tail = tail[1:].lstrip()[end:].lstrip()
        if not tail.startswith(","):
            raise ValueError("Missing continuation delimiter")
        tail = tail[1:].lstrip()
        if (expected == "references" and tail and '"comparative_mr"'.startswith(tail)
                and tail != '"comparative_mr"'):
            return fields
    key, end = decoder.raw_decode(tail)
    if key != "application_mr" or not tail[end:].lstrip().startswith(":"):
        raise ValueError("Recovery requires the diagnosed incomplete application_mr string")
    value = tail[end:].lstrip()[1:].lstrip()
    if not value.startswith('"'):
        raise ValueError("Incomplete application_mr must be a string")
    try:
        decoder.raw_decode(value)
    except json.JSONDecodeError as exc:
        if exc.msg == "Unterminated string starting at" and exc.pos == 0:
            return fields
        raise ValueError("Malformed application_mr string") from exc
    raise ValueError("Application string is complete; unsupported truncation boundary")


def prepare_recovery(work, number, partial_path):
    """Read and reconstruct original composition inputs without writes or providers.

    Parameters: work directory, entry number, retained partial path. Return bound
    evidence and a narrow continuation prompt. Hash, lineage, model, truncation,
    prior-review or schema discrepancies raise before a paid callback.
    """
    work, partial = Path(work).resolve(), Path(partial_path).resolve()
    if type(number) is not int or number < 2:
        raise ValueError("Recovery requires a numbered entry with prior chapters")
    files = {}

    def read(path, as_json=True):
        """Read an in-work evidence file and bind exact bytes for later replay."""
        path = Path(path).resolve()
        if not path.is_relative_to(work):
            raise ValueError("Recovery evidence must remain inside the work directory")
        raw = path.read_bytes()
        files[str(path.relative_to(work))] = hashlib.sha256(raw).hexdigest()
        # write_text on Windows stores CRLF; provider hashes bind original LF.
        # Keep the exact byte digest above and use normal text-mode decoding here.
        text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        return json.loads(text) if as_json else text

    plan = read(work / "plan.json")["entries"]
    item = next(x for x in plan if x["number"] == number)
    forbidden = read(work / "forbidden_formulas.json")
    if isinstance(forbidden, dict):
        forbidden = forbidden["formulas"]
    prior, used = [], set()
    for n in range(1, number):
        result = read(work / f"entry-{n:03d}.json")
        draft, review = result["draft"], result["review"]
        if (result["status"] != "READY_FOR_AUTHOR_REVIEW" or result["assessment"]["status"] != "PASS"
                or review.get("verdict") != "PASS" or review.get("outcome") != "READY"
                or review.get("reviewed_draft_sha256") != canonical_hash(draft)
                or draft["number"] != n):
            raise ValueError("Prior entries must be accepted and hash-bound")
        prior.append(draft["new_sutra"])
        used.update(case["case_id"] for case in draft["examples"])
    batch = next(b for b in planned_batches(plan) if any(x["number"] == number for x in b))
    batch_id = "entries-" + "-".join(str(x["number"]) for x in batch)
    discussion = read(work / f"{batch_id}-discussion.json")
    captured = {}
    # Use existing pure composition validation to select the exact proposal/peers.
    council = object.__new__(ResearchCouncil)
    council._bind = lambda n, base: captured.update(base=deepcopy(base))
    council._compose = lambda base, debate, proposal, peers: captured.update(request={
        **base, "discussion": debate, "speaker": "sutrakar", "proposal": proposal,
        "peer_review": peers, "stage": "composition"})
    council.compose_entry(number, {k: v for k, v in item.items() if k != "source_packet"},
                          item["source_packet"], prior, forbidden, used,
                          discussion["discussion"], discussion["proposal"], discussion["peer_review"])
    request = captured["request"]
    request_hash = digest(request)
    with sqlite3.connect((work / "council.db").as_uri() + "?mode=ro", uri=True) as db:
        binding = db.execute("SELECT request_hash FROM research_runs WHERE number=?", (number,)).fetchone()
        attempts = db.execute("SELECT attempt,request_hash,state,response_json,error FROM research_attempts WHERE number=? AND stage='composition' AND speaker='sutrakar' ORDER BY attempt", (number,)).fetchall()
    if binding != (digest({**captured["base"], "max_revisions": 1, "protocol": PROTOCOL_VERSION}),):
        raise ValueError("Original entry binding changed")
    if len(attempts) != 1 or attempts[0][1:] != (request_hash, "HARD_FAILED", "null", ERROR):
        raise ValueError("Recovery requires the exact original truncated composition attempt")
    text = read(partial, False)
    preserved = complete_prefix(text)
    metadata = read(partial.with_name(partial.name.replace(".partial.txt", ".metadata.json")))
    if (not partial.name.startswith(f"{number:03d}-composition-sutrakar-") or
            not partial.name.endswith(".partial.txt") or
            metadata.get("stage") != "composition" or metadata.get("speaker") != "sutrakar" or
            metadata.get("model") != "claude-sonnet-5-5" or metadata.get("was_truncated") is not True or
            metadata.get("finish_reason") != "max_tokens"):
        raise ValueError("Partial response identity or truncation metadata mismatch")
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    with sqlite3.connect((work / "dispatch.db").as_uri() + "?mode=ro", uri=True) as db:
        matches = [(call_id, raw) for call_id, raw in db.execute(
            "SELECT call_id,record_json FROM council_dispatch_audit WHERE status='INCOMPLETE'")
            if json.loads(raw).get("response_sha256") == text_hash]
    if len(matches) != 1:
        raise ValueError("Partial text must match one retained incomplete provider call")
    dispatch = json.loads(matches[0][1])
    if (dispatch.get("provider"), dispatch.get("model_id"), dispatch.get("role"), dispatch.get("finish_reason")) != (
            "anthropic", "claude-sonnet-5-5", "sutrakar_master", "max_tokens"):
        raise ValueError("Original provider call identity mismatch")
    prompt = ("Complete only the seven missing JSON fields listed below. Return one JSON object "
              "with exactly those keys. The six completed fields are immutable and must not be "
              "returned, replaced or rewritten. Preserve their principle and reference selection. "
              "For every selected reference write a qualified Marathi comparison under 100 words, "
              "distinguishing original meaning from modern application. Return exactly the two "
              "canonical case_ids in supplied order; no invented case facts. Provide at least three "
              "specific dos and three donts, application_mr, actionable action_mr and summary_mr. "
              "No English quotations. Return complete JSON within the output limit.\nINPUT\n" +
              json.dumps({"missing_fields": MISSING, "completed_fields": preserved,
                          "brief": request["brief"], "sources": request["sources"]}, ensure_ascii=False))
    if len(preserved) == 10:
        prompt = ("Return one complete JSON object with ONLY application_mr, action_mr and summary_mr, "
                  "each a nonempty Marathi string. The ten completed fields below are immutable: "
                  "do not return, replace or rewrite them. Complete the business application, "
                  "actionable exercise and brief summary using the existing principle and supplied "
                  "canonical cases only. Do not add factual claims or English quotations. "
                  "Do not return comparison, case-selection, dos or donts fields.\nINPUT\n" +
                  json.dumps({"missing_fields": MISSING[4:], "completed_fields": preserved,
                              "brief": request["brief"], "sources": request["sources"]}, ensure_ascii=False))
    return {"number": number, "request": request, "request_hash": request_hash,
            "original_attempts": [list(a) for a in attempts], "input_sha256": files,
            "dispatch_call_id": matches[0][0], "dispatch_record_sha256": hashlib.sha256(matches[0][1].encode()).hexdigest(),
            "preserved": preserved, "model_id": "claude-sonnet-5-5", "effort": "medium",
            "max_output_tokens": 6000, "system": SYSTEM, "prompt": prompt}


def _validate_patch(bound, patch):
    """Merge only missing fields, enrich canonical cases and run both acceptance gates."""
    preserved = set(bound["preserved"])
    if preserved not in (set(PRESERVED), set(PRESERVED + MISSING[:4])):
        raise ValueError("Unsupported preserved-field boundary")
    remaining = set(PRESERVED + MISSING) - preserved
    if not isinstance(patch, dict) or set(patch) != remaining:
        raise ValueError("Continuation must contain exactly the remaining fields")
    request = bound["request"]
    answer = complete_entry({**deepcopy(bound["preserved"]), **deepcopy(patch)}, request)
    answer = _check_answer("composition", "sutrakar", answer, request)
    assessment = assess_research_entry(answer, request["sources"], request["prior_formulas"],
                                       request["forbidden_originals"], set(request["used_case_ids"]))
    if assessment["status"] != "PASS":
        raise ValueError("Continuation assessment failed: " + "; ".join(assessment["issues"]))
    for comparison in answer["comparative_mr"]:
        if len(comparison["explanation_mr"].split()) >= 100:
            raise ValueError("Continuation comparison must remain under 100 words")
    if any(answer[k] != bound["preserved"][k] for k in bound["preserved"]):
        raise ValueError("Continuation changed a preserved field")
    return answer, assessment


def _decode_response(response):
    """Require a complete same-Sonnet response envelope; return its parsed patch."""
    if (response.get("provider"), response.get("model_id"), response.get("was_truncated")) != (
            "anthropic", "claude-sonnet-5-5", False) or response.get("finish_reason") == "max_tokens":
        raise ValueError("Continuation provider changed or output truncated")
    return parse_object(response["content"])


def recover_comparison_field_alias(work, number, partial_path):
    """Explicitly normalize only diagnosed comparison-key aliases without a call.

    Parameters: original work directory, number and partial path. Return an
    immutable zero-call audit record. Preserve all values, FAILED continuation
    bytes and original HARD_FAILED evidence. Wrong fields/IDs, other assessment
    failures or changed bindings raise; successful drafts still need review.
    """
    bound = prepare_recovery(work, number, partial_path)
    path = Path(work).resolve() / "council.db"
    alias_table = "research_comparison_alias_recoveries"
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(f"SELECT state,binding_json,response_json,record_json,error FROM {TABLE} WHERE number=?",
                         (number,)).fetchone()
        if (not row or row[0] != "FAILED" or row[3] is not None or
                json.loads(row[1]) != bound):
            raise ValueError("Alias recovery requires the unchanged FAILED continuation")
        response = json.loads(row[2])
        patch = _decode_response(response)
        comparisons = patch.get("comparative_mr") if isinstance(patch, dict) else None
        refs = bound["preserved"]["references"]
        if (not isinstance(comparisons, list) or not comparisons or
                any(not isinstance(c, dict) or set(c) != {"reference_id", "text_mr"} or
                    not isinstance(c["reference_id"], str) or c["reference_id"] not in refs or
                    not isinstance(c["text_mr"], str) or not c["text_mr"].strip()
                    for c in comparisons)):
            raise ValueError("Only exact comparison aliases with retained reference IDs qualify")
        expected_error = "ValueError: Continuation assessment failed: " + "; ".join(
            ["Comparison requires a nonempty source_id"] * len(comparisons) +
            [f"Missing comparison for reference: {ref}" for ref in sorted(set(refs))])
        if row[4] != expected_error:
            raise ValueError("Alias recovery requires only the diagnosed comparison-field error")
        try:
            _validate_patch(bound, patch)
        except ValueError as exc:
            if f"ValueError: {exc}" != expected_error:
                raise ValueError("Retained response no longer reproduces the diagnosed error") from exc
        else:
            raise ValueError("Retained response does not require alias recovery")
        normalized = deepcopy(patch)
        normalized["comparative_mr"] = [{"source_id": c["reference_id"], "explanation_mr": c["text_mr"]}
                                         for c in comparisons]
        answer, assessment = _validate_patch(bound, normalized)
        record = {"kind": "comparison-field-alias-v1", "number": number,
                  "binding_sha256": digest(bound), "request_sha256": bound["request_hash"],
                  "failed_continuation_sha256": digest(list(row)),
                  "raw_response_sha256": hashlib.sha256(row[2].encode()).hexdigest(),
                  "normalized_patch_sha256": digest(normalized), "composition_sha256": digest(answer),
                  "normalizations": [{"index": i, "reference_id": "source_id", "text_mr": "explanation_mr"}
                                     for i in range(len(comparisons))],
                  "assessment": assessment, "provider_calls": 0, "independent_review": "PENDING"}
        db.execute(f"CREATE TABLE IF NOT EXISTS {alias_table} (number INTEGER PRIMARY KEY,record_json TEXT NOT NULL)")
        saved = db.execute(f"SELECT record_json FROM {alias_table} WHERE number=?", (number,)).fetchone()
        stage = db.execute("SELECT request_hash,response_json FROM research_stages WHERE number=? AND stage='composition' AND speaker='sutrakar'", (number,)).fetchone()
        if saved:
            if json.loads(saved[0]) != record or stage != (bound["request_hash"], _json(answer)):
                raise ValueError("Alias recovery evidence or successful checkpoint changed")
            return record
        if stage:
            raise ValueError("Composition already exists without this alias recovery")
        if prepare_recovery(work, number, partial_path) != bound:
            raise ValueError("Alias recovery inputs changed during validation")
        db.execute("INSERT INTO research_stages VALUES (?,'composition','sutrakar',?,?)",
                   (number, bound["request_hash"], _json(answer)))
        db.execute(f"INSERT INTO {alias_table} VALUES (?,?)", (number, _json(record)))
    return record


def recover_truncated_composition(work, number, partial_path, call):
    """Explicitly reserve and execute one budgeted continuation, or verify its replay.

    Callback signature: call(system, prompt, model_id=..., effort='medium',
    max_output_tokens=6000), returning ProviderResponse or equivalent metadata dict.
    The parent must use the existing dispatcher/Claude cap. Return audit metadata.
    Failures persist; RUNNING/FAILED cannot retry. Original HARD_FAILED and files
    are never edited. Successful insertion is atomic and does not grant review PASS.
    """
    bound = prepare_recovery(work, number, partial_path)
    path = Path(work).resolve() / "council.db"
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (number INTEGER PRIMARY KEY, state TEXT NOT NULL, binding_json TEXT NOT NULL, response_json TEXT, record_json TEXT, error TEXT)")
        row = db.execute(f"SELECT state,binding_json,response_json,record_json,error FROM {TABLE} WHERE number=?", (number,)).fetchone()
        stage = db.execute("SELECT request_hash,response_json FROM research_stages WHERE number=? AND stage='composition' AND speaker='sutrakar'", (number,)).fetchone()
        if row:
            if row[0] != "COMPLETE" or row[4] is not None or json.loads(row[1]) != bound:
                raise RuntimeError("Continuation unavailable or inputs changed; no automatic retry")
            response = json.loads(row[2])
            answer, assessment = _validate_patch(bound, _decode_response(response))
            record = {"kind": "truncated-composition-continuation-v1", "number": number,
                      "binding_sha256": digest(bound), "response_sha256": digest(response),
                      "composition_sha256": digest(answer), "assessment": assessment,
                      "provider_calls": 1, "independent_review": "PENDING"}
            if json.loads(row[3]) != record or stage != (bound["request_hash"], _json(answer)):
                raise ValueError("Continuation audit or successful checkpoint changed")
            return record
        if stage:
            raise ValueError("A composition checkpoint already exists without this recovery")
        db.execute(f"INSERT INTO {TABLE} VALUES (?,'RUNNING',?,NULL,NULL,NULL)", (number, _json(bound)))
    response = None
    try:
        raw = call(bound["system"], bound["prompt"], model_id=bound["model_id"],
                   effort=bound["effort"], max_output_tokens=bound["max_output_tokens"])
        response = raw if isinstance(raw, dict) else {k: getattr(raw, k) for k in
                    ("provider", "model_id", "was_truncated", "finish_reason", "content")}
        answer, assessment = _validate_patch(bound, _decode_response(response))
        if prepare_recovery(work, number, partial_path) != bound:
            raise ValueError("Continuation evidence changed during callback")
        record = {"kind": "truncated-composition-continuation-v1", "number": number,
                  "binding_sha256": digest(bound), "response_sha256": digest(response),
                  "composition_sha256": digest(answer), "assessment": assessment,
                  "provider_calls": 1, "independent_review": "PENDING"}
        with sqlite3.connect(path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(f"SELECT state,binding_json FROM {TABLE} WHERE number=?", (number,)).fetchone()
            attempts = db.execute("SELECT attempt,request_hash,state,response_json,error FROM research_attempts WHERE number=? AND stage='composition' AND speaker='sutrakar' ORDER BY attempt", (number,)).fetchall()
            if row != ("RUNNING", _json(bound)) or [list(a) for a in attempts] != bound["original_attempts"]:
                raise ValueError("Continuation reservation or original failure changed")
            db.execute("INSERT INTO research_stages VALUES (?,'composition','sutrakar',?,?)",
                       (number, bound["request_hash"], _json(answer)))
            db.execute(f"UPDATE {TABLE} SET state='COMPLETE',response_json=?,record_json=? WHERE number=?",
                       (_json(response), _json(record), number))
        return record
    except Exception as exc:
        with sqlite3.connect(path) as db:
            db.execute(f"UPDATE {TABLE} SET state='FAILED',response_json=?,error=? WHERE number=? AND state='RUNNING'",
                       (_json(response), f"{type(exc).__name__}: {str(exc)[:500]}", number))
        raise RuntimeError("Composition continuation failed; no automatic retry") from exc

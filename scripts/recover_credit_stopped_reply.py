"""One explicitly confirmed recovery of the batch 43–47 credit-stopped reply.

No SDK, credentials or automatic retry. The parent supplies the existing budgeted
Claude callback only after credit confirmation. All original evidence is retained.
"""

import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path

from scripts.run_research_book import SYSTEM, planned_batches, prompt_payload, stage_contract
from scripts.run_book_council_v19 import parse_object
from src.orchestration.independent_review import canonical_hash
from src.orchestration.research_council import PROTOCOL_VERSION, VOICES, _check_answer, _json

BATCH_ID = "entries-43-44-45-46-47"
REQUEST_HASH = "e806461d1d53460b18785557a2dfac94576659cde0023acbe408b2c61ee40836"
CALL_ID = "c554df2b-d4bd-4ef1-9f94-213c0e4951ab"
ERROR = ("ProviderError: [anthropic:claude-sonnet-5-5] Anthropic generation failed: Error code: 400 - "
         "{'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'Your credit balance "
         "is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase "
         "credits.'}, 'request_id': 'req_011ChAedgtGn1pd1B1oQz9w1'}")
TABLE = "research_credit_reply_recoveries"


def digest(value):
    """Return the council's canonical JSON hash, including exact string values."""
    return hashlib.sha256(_json(value).encode()).hexdigest()


def batch_path(work):
    """Resolve the one authorized batch checkpoint filename, without touching disk."""
    return Path(work).resolve() / f"council.db.batch-{digest(BATCH_ID)}.sqlite3"


def prepare_recovery(work):
    """Reconstruct and verify the exact failed reply using read-only evidence.

    Parameter: work directory. Return bound inputs and unchanged original reply
    prompt. Reject drift, other failures, missing peers, changed request hashes or
    dispatch identity before any write/provider call; inspect retained rows to debug.
    """
    work = Path(work).resolve()
    files = {}

    def read(name):
        """Read a known evidence file and bind its bytes; return decoded JSON."""
        raw = (work / name).read_bytes()
        files[name] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw.decode("utf-8"))

    plan = read("plan.json")["entries"]
    batches = planned_batches(plan)
    batch = next((b for b in batches if [x["number"] for x in b] == list(range(43, 48))), None)
    if batch is None:
        raise ValueError("Authorized 43–47 batch is absent or changed")
    forbidden = read("forbidden_formulas.json")
    if isinstance(forbidden, dict):
        forbidden = forbidden["formulas"]
    prior = []
    for n in range(1, 43):
        result = read(f"entry-{n:03d}.json")
        draft, review = result["draft"], result["review"]
        if (draft["number"] != n or result["status"] != "READY_FOR_AUTHOR_REVIEW" or
                result["assessment"]["status"] != "PASS" or review.get("outcome") != "READY" or
                review.get("verdict") != "PASS" or review.get("reviewed_draft_sha256") != canonical_hash(draft)):
            raise ValueError("Prior chapters must remain accepted and hash-bound")
        prior.append(draft["new_sutra"])
    briefs = [{k: v for k, v in item.items() if k != "source_packet"} for item in batch]
    packets = {str(item["number"]): item["source_packet"] for item in batch}
    base = {"number": 0, "brief": {"batch_id": BATCH_ID}, "sources": packets,
            "scope": "batch", "batch_id": BATCH_ID, "briefs": briefs,
            "entry_numbers": list(range(43, 48)), "sources_by_entry": packets,
            "prior_formulas": prior, "forbidden_originals": forbidden, "used_case_ids": []}
    with sqlite3.connect(batch_path(work).as_uri() + "?mode=ro", uri=True) as db:
        binding = db.execute("SELECT request_hash FROM research_runs WHERE number=0").fetchone()
        rows = db.execute("SELECT stage,speaker,request_hash,response_json FROM research_stages WHERE number=0").fetchall()
        attempts = db.execute("SELECT attempt,request_hash,state,response_json,error FROM research_attempts WHERE number=0 AND stage='reply' AND speaker='sutrakar' ORDER BY attempt").fetchall()
    if binding != (digest({**base, "max_revisions": 1, "protocol": PROTOCOL_VERSION}),):
        raise ValueError("Original batch binding changed")
    if attempts != [(1, REQUEST_HASH, "HARD_FAILED", "null", ERROR)]:
        raise ValueError("Only the exact diagnosed credit-stopped reply is eligible")
    saved = {(stage, speaker): (request_hash, raw) for stage, speaker, request_hash, raw in rows}
    discussion, verified_rows = {}, []
    for stage in ("position", "challenge", "reply"):
        answers = {}
        for speaker in VOICES:
            if stage == "reply" and speaker == "sutrakar":
                continue
            request = {**base, "discussion": deepcopy(discussion), "stage": stage, "speaker": speaker}
            stored = saved.get((stage, speaker))
            if not stored or stored[0] != digest(request):
                raise ValueError("Completed sibling request hash changed or stage missing")
            answers[speaker] = _check_answer(stage, speaker, json.loads(stored[1]), request)
            verified_rows.append([stage, speaker, *stored])
        if stage != "reply":
            discussion[stage] = answers
    request = {**base, "discussion": discussion, "stage": "reply", "speaker": "sutrakar"}
    if digest(request) != REQUEST_HASH:
        raise ValueError("Reconstructed reply differs from the original failed request")
    with sqlite3.connect((work / "dispatch.db").as_uri() + "?mode=ro", uri=True) as db:
        dispatch = db.execute("SELECT run_id,reservation_usd,status,record_json FROM council_dispatch_audit WHERE call_id=?", (CALL_ID,)).fetchone()
    if not dispatch or dispatch[:3] != ("full-book-v26", 0.090762, "FAILED"):
        raise ValueError("Original failed dispatch reservation changed")
    meta = json.loads(dispatch[3])
    if (meta.get("provider"), meta.get("model_id"), meta.get("role"), meta.get("error_type")) != (
            "anthropic", "claude-sonnet-5-5", "sutrakar_master", "ProviderError"):
        raise ValueError("Original dispatch provider identity changed")
    prompt = stage_contract("reply", request) + "\nINPUT\n" + json.dumps(prompt_payload(request), ensure_ascii=False)
    return {"kind": "credit-stopped-reply-v1", "request_hash": REQUEST_HASH, "request": request,
            "input_sha256": files, "original_attempts": [list(a) for a in attempts],
            "siblings_sha256": digest(verified_rows), "original_dispatch_sha256": digest(list(dispatch)),
            "original_call_id": CALL_ID, "system": SYSTEM, "prompt": prompt,
            "model_id": "claude-sonnet-5-5", "effort": "medium", "max_output_tokens": 4500}


def _answer(response, bound):
    """Validate complete same-Sonnet output and exact three-peer/five-entry coverage."""
    if (response.get("provider"), response.get("model_id"), response.get("was_truncated")) != (
            "anthropic", "claude-sonnet-5-5", False) or response.get("finish_reason") == "max_tokens":
        raise ValueError("Credit recovery response changed provider or is truncated")
    return _check_answer("reply", "sutrakar", parse_object(response["content"]), bound["request"])


def recover_credit_stopped_reply(work, call, *, credits_confirmed=False):
    """Reserve one explicit retry after confirmation, preserving every failed record.

    Parameters: work directory, budgeted callback(system,prompt,model_id,effort,
    max_output_tokens), and literal True after the user's credit confirmation.
    Callback returns ProviderResponse or equivalent metadata dict. Return audit
    record. FAILED/RUNNING never retry; replay revalidates all hashes and the
    successful stage. No core/ledger rows are removed or overwritten.
    """
    if credits_confirmed is not True or not callable(call):
        raise ValueError("Explicit credit confirmation and a budgeted callback are required")
    bound = prepare_recovery(work)
    path = batch_path(work)

    def record_for(response, answer):
        """Bind original evidence, full retained response and validated stage output."""
        return {"kind": bound["kind"], "request_hash": REQUEST_HASH,
                "binding_sha256": digest(bound), "response_sha256": digest(response),
                "answer_sha256": digest(answer), "provider_calls": 1,
                "credits_confirmed": True, "author_approval": "PENDING"}

    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (request_hash TEXT PRIMARY KEY,state TEXT NOT NULL,binding_json TEXT NOT NULL,response_json TEXT,record_json TEXT,error TEXT)")
        row = db.execute(f"SELECT state,binding_json,response_json,record_json,error FROM {TABLE} WHERE request_hash=?", (REQUEST_HASH,)).fetchone()
        stage = db.execute("SELECT request_hash,response_json FROM research_stages WHERE number=0 AND stage='reply' AND speaker='sutrakar'").fetchone()
        if row:
            if row[0] != "COMPLETE" or row[4] is not None or json.loads(row[1]) != bound:
                raise RuntimeError("Credit recovery unavailable or changed; no automatic retry")
            response = json.loads(row[2])
            answer = _answer(response, bound)
            record = record_for(response, answer)
            if json.loads(row[3]) != record or stage != (REQUEST_HASH, _json(answer)):
                raise ValueError("Credit recovery audit or successful stage changed")
            return record
        if stage:
            raise ValueError("Successful reply already exists without this recovery")
        db.execute(f"INSERT INTO {TABLE} VALUES (?,'RUNNING',?,NULL,NULL,NULL)", (REQUEST_HASH, _json(bound)))
    response = None
    try:
        raw = call(bound["system"], bound["prompt"], model_id=bound["model_id"],
                   effort=bound["effort"], max_output_tokens=bound["max_output_tokens"])
        response = raw if isinstance(raw, dict) else {k: getattr(raw, k) for k in
                    ("provider", "model_id", "was_truncated", "finish_reason", "content")}
        answer = _answer(response, bound)
        if prepare_recovery(work) != bound:
            raise ValueError("Credit recovery evidence changed during callback")
        record = record_for(response, answer)
        with sqlite3.connect(path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(f"SELECT state,binding_json FROM {TABLE} WHERE request_hash=?", (REQUEST_HASH,)).fetchone()
            attempts = db.execute("SELECT attempt,request_hash,state,response_json,error FROM research_attempts WHERE number=0 AND stage='reply' AND speaker='sutrakar' ORDER BY attempt").fetchall()
            if row != ("RUNNING", _json(bound)) or [list(a) for a in attempts] != bound["original_attempts"]:
                raise ValueError("Credit recovery reservation or original failure changed")
            db.execute("INSERT INTO research_stages VALUES (0,'reply','sutrakar',?,?)", (REQUEST_HASH, _json(answer)))
            db.execute(f"UPDATE {TABLE} SET state='COMPLETE',response_json=?,record_json=? WHERE request_hash=?",
                       (_json(response), _json(record), REQUEST_HASH))
        return record
    except Exception as exc:
        with sqlite3.connect(path) as db:
            db.execute(f"UPDATE {TABLE} SET state='FAILED',response_json=?,error=? WHERE request_hash=? AND state='RUNNING'",
                       (_json(response), f"{type(exc).__name__}: {str(exc)[:500]}", REQUEST_HASH))
        raise RuntimeError("Credit reply recovery failed; no automatic retry") from exc

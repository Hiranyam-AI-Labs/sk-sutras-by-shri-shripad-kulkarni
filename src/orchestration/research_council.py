"""Offline, durable four-voice research protocol; all model wiring belongs to callers.

Callbacks return JSON dictionaries (including any parent usage metadata). The
parent parses provider JSON and enriches compositions with its immutable case
pack before returning them. This module never approves or publishes an entry.
"""

import hashlib
import json
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from src.orchestration.research_acceptance import _devanagari_word


VOICES = ("narada", "shandilya", "researcher", "sutrakar")
TEXT_FIELDS = (
    "id", "title_mr", "grammar_mr", "translation_mr", "application_mr",
    "action_mr", "summary_mr",
)
PROTOCOL_VERSION = 3
SOURCE_FIRST_SELECTION = "source-first-selection-v1"
_RETRY_AUTHORIZATION_SCHEMA = """
    CREATE TABLE IF NOT EXISTS research_schema_retry_authorizations (
        number INTEGER NOT NULL, stage TEXT NOT NULL, speaker TEXT NOT NULL,
        request_hash TEXT NOT NULL, reason TEXT NOT NULL, authorized_at TEXT NOT NULL,
        PRIMARY KEY (number, stage, speaker))
"""


def authorize_schema_retry(path: Path, number: int, stage: str, speaker: str, reason: str) -> dict:
    """Purpose: authorize exactly one extra attempt for one exhausted schema key.

    Parameters: path, existing entry/batch SQLite file; number, entry number or
    batch marker 0; stage/speaker, exact failed key; reason, nonblank audit reason.
    Returns: key, bound request_hash, reason, UTC authorized_at and max_attempts=3.
    Failures: ValueError unless exactly attempts 1 and 2 are FAILED schema errors
    with identical hashes, no successful stage and no prior authorization. HARD_FAILED,
    RUNNING, incomplete or already retried keys are ineligible. SQLite errors
    propagate. No provider, callback, input hash, protocol, or failed row changes.
    The third durable attempt reservation consumes the allowance even on failure.
    """
    if type(number) is not int or number < 0 or any(
        not isinstance(value, str) or not value.strip() for value in (stage, speaker, reason)
    ):
        raise ValueError("Exact stage key and a nonempty retry reason are required")
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError("Schema retry requires an existing checkpoint database")
    key = (number, stage, speaker)
    with sqlite3.connect(path.as_uri() + "?mode=rw", uri=True) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(_RETRY_AUTHORIZATION_SCHEMA)
        if db.execute("SELECT 1 FROM research_schema_retry_authorizations "
                      "WHERE number=? AND stage=? AND speaker=?", key).fetchone():
            raise ValueError("Schema retry already authorized; maximum once per stage key")
        if db.execute("SELECT 1 FROM research_stages WHERE number=? AND stage=? AND speaker=?",
                      key).fetchone():
            raise ValueError("Successful stages cannot receive schema retry authorization")
        rows = db.execute("SELECT attempt,request_hash,state,error FROM research_attempts "
                          "WHERE number=? AND stage=? AND speaker=? ORDER BY attempt", key).fetchall()
        if (len(rows) != 2 or [row[0] for row in rows] != [1, 2]
                or any(row[2] != "FAILED" or not isinstance(row[3], str) or
                       not row[3].startswith(("ValueError:", "TypeError:")) for row in rows)
                or rows[0][1] != rows[1][1]):
            raise ValueError("Schema retry requires exactly two matching FAILED schema attempts")
        timestamp = datetime.now(timezone.utc).isoformat()
        db.execute("INSERT INTO research_schema_retry_authorizations VALUES (?,?,?,?,?,?)",
                   (*key, rows[0][1], reason.strip(), timestamp))
    return {"number": number, "stage": stage, "speaker": speaker,
            "request_hash": rows[0][1], "reason": reason.strip(),
            "authorized_at": timestamp, "max_attempts": 3}


def _json(value: object) -> str:
    """Purpose: canonical serialization. Parameters: value, JSON data.

    Returns: deterministic Unicode JSON. Failures: TypeError/ValueError for
    non-JSON values or nonfinite numbers; provider parsing stays with the parent.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _short_sutra(value: object) -> None:
    """Purpose: cheap formula gate. Parameters: value, string or text object.

    Returns: None for 2–4 words and at most 32 characters (excluding terminal
    dandas). Failures: ValueError for invalid shape; no grammar claims are made.
    """
    if isinstance(value, dict):
        value = value.get("text")
    text = value.strip().strip("।॥").strip() if isinstance(value, str) else ""
    if not 2 <= len(re.findall(r"[^\s।॥]+", text)) <= 4 or len(text) > 32:
        raise ValueError("Short-sutra gate requires 2–4 words and <=32 characters")
    if "," in text or "，" in text:
        raise ValueError("Short-sutra gate rejects compound sentences")


def _strings(value: object) -> list[str]:
    """Purpose: extract literal evidence. Parameters: value, nested JSON data.

    Returns: string leaves only, never dictionary keys or serialized syntax.
    Failures: none for JSON inputs; non-container/non-string values yield [].
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def _field_value(target: dict, field: str) -> object:
    """Purpose: resolve issue evidence. Parameters: target and dotted field path.

    Returns: the field value, supporting list indices and bracket notation.
    Failures: ValueError if the path does not exist in this exact target.
    """
    if field in target:
        return target[field]
    value = target
    try:
        for part in field.replace("[", ".").replace("]", "").split("."):
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid review: unknown current field {field}") from exc


def _check_review(answer: dict, target: dict) -> None:
    """Purpose: validate non-editing criticism. Parameters: answer and current target.

    Returns: None for a consistent verdict and structured, literally grounded
    issues. Failures: ValueError for edits, invalid verdicts, or absent quotes.
    """
    if answer.get("verdict") not in ("PASS", "REVIEW_REQUIRED"):
        raise ValueError("Invalid review verdict; expected PASS or REVIEW_REQUIRED")
    if {"draft", "entry", "new_sutra", "revised_draft", "edited_draft", "corrected_draft"} & answer.keys():
        raise ValueError("Invalid review: validator/reviewer cannot edit the draft")
    issues = answer.get("issues")
    if not isinstance(issues, list):
        raise ValueError("Invalid review: issues must be a list")
    if (answer["verdict"] == "PASS") != (not issues):
        raise ValueError("Invalid review: verdict and issues disagree")
    for issue in issues:
        if not isinstance(issue, dict) or any(
            not isinstance(issue.get(key), str) or not issue[key].strip()
            for key in ("field", "quote", "reason", "severity")
        ):
            raise ValueError("Invalid review: each issue needs field, quote, reason, severity")
        value = _field_value(target, issue["field"])
        if not any(issue["quote"] in text for text in _strings(value)):
            raise ValueError("Invalid review: quote absent from current draft field")


def _numbered(records: object, numbers: list[int], label: str) -> dict[int, dict]:
    """Purpose: require exact numbered coverage. Parameters: records, numbers, label.

    Returns: number-indexed records. Failures: ValueError for missing, extra,
    duplicate, noninteger or malformed records; booleans are not entry numbers.
    """
    if not isinstance(records, list) or any(not isinstance(r, dict) or
                                            type(r.get("number")) is not int for r in records):
        raise ValueError(f"{label} requires numbered records")
    result = {record["number"]: record for record in records}
    if len(result) != len(records) or set(result) != set(numbers):
        raise ValueError(f"{label} requires exact entry numbers {numbers}")
    return result


def _coverage(records: object, numbers: list[int], label: str) -> None:
    """Purpose: require substantive per-entry discussion. Parameters: records,
    numbers, label. Returns: None. Failures: ValueError for missing/extra keys
    or empty evidence. Structural coverage cannot certify semantic relevance.
    """
    if not isinstance(records, dict) or set(records) != {str(n) for n in numbers}:
        raise ValueError(f"{label} requires exact entry-number string keys")
    if any(not any(text.strip() for text in _strings(value)) for value in records.values()):
        raise ValueError(f"{label} requires substantive coverage for every entry")


def _source_pair_ids(packet: dict) -> tuple[set[str], set[str]]:
    """Validate opt-in packet IDs, returning the pair and all registered IDs.

    source_pair_ids must name exactly one N<number> and one S<number>, each
    present in references=[{id: ...}]. This checks reference identity only;
    source fidelity and suitability remain discussion/review responsibilities.
    """
    pair = packet.get("source_pair_ids")
    references = packet.get("references")
    if (not isinstance(pair, list) or len(pair) != 2
            or any(not isinstance(item, str) for item in pair)
            or sum(bool(re.fullmatch(r"N[1-9][0-9]*", item)) for item in pair) != 1
            or sum(bool(re.fullmatch(r"S[1-9][0-9]*", item)) for item in pair) != 1):
        raise ValueError("Source-first packet requires one N and one S source_pair_ids")
    if (not isinstance(references, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("id"), str)
            or not item["id"].strip() for item in references)):
        raise ValueError("Source-first packet requires registered references with IDs")
    ids = [item["id"] for item in references]
    if len(ids) != len(set(ids)) or not set(pair).issubset(ids):
        raise ValueError("Source pair must occur in unique registered references")
    return set(pair), set(ids)


def _check_selection(proposal: dict, packet: dict) -> bool:
    """Validate opt-in disposition; return True only for an explicit rejection.

    REJECT omits proposed_sutra and supplies rejection_reason (at least five
    words). That minimum is a structural floor, not semantic certification;
    the same three peers review the reason. ACCEPT retains the legacy formula
    and derivation gates plus registered source IDs including the exact pair.
    """
    pair, registered = _source_pair_ids(packet)
    if proposal.get("decision") == "REJECT":
        reason = proposal.get("rejection_reason")
        if (not isinstance(reason, str) or len(reason.split()) < 5
                or "proposed_sutra" in proposal):
            raise ValueError("REJECT requires an explanatory five-word reason and no proposed_sutra")
        return True
    if proposal.get("decision") != "ACCEPT" or "rejection_reason" in proposal:
        raise ValueError("Source-first proposal requires unambiguous ACCEPT or REJECT")
    selected = proposal.get("selected_source_ids")
    if (not isinstance(selected, list) or any(not isinstance(item, str) for item in selected)
            or len(selected) != len(set(selected)) or not pair.issubset(selected)
            or not set(selected).issubset(registered)):
        raise ValueError("ACCEPT must reference both source-pair IDs and only registered sources")
    return False


def _check_batch(stage: str, speaker: str, answer: dict, request: dict) -> dict:
    """Purpose: enforce batch-wide coverage. Parameters: stage, speaker, answer,
    request. Returns: validated answer. Failures: ValueError for incomplete
    discussion, proposal, or reviews; no model calls or semantic claims occur.
    """
    numbers = request["entry_numbers"]
    if stage == "position":
        _coverage(answer.get("positions"), numbers, "Batch positions")
    elif stage in ("challenge", "reply"):
        key = "challenges" if stage == "challenge" else "answers"
        records = answer.get(key)
        if not isinstance(records, dict) or set(records) != set(VOICES) - {speaker}:
            raise ValueError(f"Batch {stage} requires exact other three role keys")
        for peer, values in records.items():
            _coverage(values, numbers, f"{stage}/{speaker}/{peer}")
    elif stage == "proposal":
        proposals = _numbered(answer.get("proposals"), numbers, "Batch proposals")
        for proposal in proposals.values():
            if request.get("source_first_selection") == SOURCE_FIRST_SELECTION:
                if _check_selection(proposal, request["sources_by_entry"][str(proposal["number"])]):
                    continue
            _short_sutra(proposal.get("proposed_sutra"))
            if not isinstance(proposal.get("derivation"), str) or not proposal["derivation"].strip():
                raise ValueError("Batch proposal requires a derivation for every entry")
            selected = proposal.get("selected_source_ids")
            if not isinstance(selected, list) or any(not isinstance(s, str) or not s.strip() for s in selected):
                raise ValueError("Batch proposal selected_source_ids must be a string list")
    elif stage == "peer_review":
        proposals = _numbered(request["proposal"]["proposals"], numbers, "Batch proposals")
        reviews = _numbered(answer.get("reviews"), numbers, "Batch peer reviews")
        for number, review in reviews.items():
            _check_review(review, proposals[number])
    else:
        raise ValueError(f"Unknown batch stage {stage}")
    return answer


def _check_answer(stage: str, speaker: str, answer: object, request: dict) -> dict:
    """Purpose: enforce stage schemas. Parameters: stage, speaker, answer, request.

    Returns: validated dictionary, normalizing direct peer maps only. Failures:
    ValueError/TypeError for malformed JSON data, shape, coverage, or reviews.
    """
    if not isinstance(answer, dict) or not answer:
        raise ValueError(f"Empty or malformed {stage}/{speaker} dictionary")
    _json(answer)
    if request.get("scope") == "batch":
        return _check_batch(stage, speaker, answer, request)
    if stage in ("challenge", "reply"):
        key = "challenges" if stage == "challenge" else "answers"
        peers = set(VOICES) - {speaker}
        if set(answer) == peers:
            answer = {key: answer}
        mapping = answer.get(key)
        if not isinstance(mapping, dict) or set(mapping) != peers:
            raise ValueError(f"{speaker} {stage} requires exact other three role keys")
        if any(not _strings(value) or not any(t.strip() for t in _strings(value))
               for value in mapping.values()):
            raise ValueError(f"{stage} requires substantive answers for every peer")
    elif stage == "position":
        if not any(text.strip() for key, value in answer.items()
                   if key != "usage" for text in _strings(value)):
            raise ValueError("Position requires a compact substantive record")
    elif stage == "proposal":
        _short_sutra(answer.get("proposed_sutra"))
    elif stage.startswith("composition"):
        _short_sutra(answer.get("new_sutra"))
        if not isinstance(answer.get("new_sutra"), str):
            raise ValueError("Composition new_sutra must be a string")
        if any(not isinstance(answer.get(key), str) or not answer[key].strip()
               for key in TEXT_FIELDS):
            raise ValueError("Composition requires complete nonempty prose fields")
        if type(answer.get("number")) is not int or answer["number"] != request["number"]:
            raise ValueError("Composition number must match the requested entry")
        chapter = answer.get("chapter")
        if not ((isinstance(chapter, str) and chapter.strip()) or
                (type(chapter) is int and chapter > 0)):
            raise ValueError("Composition requires a chapter label or positive integer")
        for key in ("examples", "dos_mr", "donts_mr", "references", "comparative_mr", "exposition"):
            if not isinstance(answer.get(key), list):
                raise ValueError(f"Composition requires a {key} list")
        if not answer["exposition"] or any(not isinstance(p, str) or not p.strip()
                                           for p in answer["exposition"]):
            raise ValueError("Composition exposition requires nonempty paragraphs")
        # Case provenance, word counts, originality, and source sufficiency are
        # assessed by the parent's policy. A Narada/Shandilya pair is optional.
    elif stage == "peer_review":
        _check_review(answer, request["proposal"])
    elif stage.startswith("independent_review"):
        _check_review(answer, request["draft"])
    elif stage.startswith("assessment"):
        if not isinstance(answer.get("status"), str) or not answer["status"].strip():
            raise ValueError("Assessment requires a status")
        if not isinstance(answer.get("issues"), list):
            raise ValueError("Assessment requires an issues list")
        if answer["status"] == "PASS" and answer["issues"]:
            raise ValueError("Assessment PASS cannot contain issues")
    return answer


class ResearchCouncil:
    """Four parallel voices, an isolated validator, and at most two draft repairs.

    SQLite retains raw responses, usage, exceptions, attempt reservations, and
    exact successful stage outputs. Failed attempts consume the same two-call
    budget across process resumes. Non-ValueError callback failures are terminal;
    ValueError is reserved for the parent's JSON/schema rejection. An interrupted in-flight call fails closed;
    its outcome must be reconciled before using that database again.
    """

    def __init__(self, path: Path, voices: Mapping[str, Callable],
                 validator: Callable, assessor: Callable, max_revisions: int = 2,
                 policy_corrections: Mapping[int, str] | None = None,
                 final_review: Callable | None = None, draft_overrides: Mapping[int, dict] | None = None,
                 editorial_additions: Mapping[int, dict] | None = None,
                 source_first_selection: bool = False):
        """Purpose: bind parent callbacks and initialize the checkpoint store.

        Parameters: path, SQLite file; voices, exact four callbacks; validator,
        independent payload callback; assessor, five-argument deterministic check;
        max_revisions, 0–2 additional composition/review cycles; policy_corrections,
        optional explicit entry-number -> diagnostic-reason whitelist for one v1
        final-review correction. It does not alter existing input/protocol hashes;
        the reason is bound to the new correction-stage hash. final_review is an
        optional opinion-blind, versioned validator callback; draft_overrides maps
        numbers to immutable corrected candidates. editorial_additions maps entry
        numbers to seed_sha256/paragraph_mr for explicit local word-count repairs.
        None of these options overwrite paid composition rows.
        source_first_selection=True opts batch discussion into explicit ACCEPT/
        REJECT proposals; packets declare source_pair_ids and references (see
        run_batch_discussion). False leaves legacy hashes and schemas unchanged.
        Returns: None.
        Failures: ValueError for invalid configuration; filesystem/SQLite errors.
        """
        if set(voices) != set(VOICES) or not all(callable(v) for v in voices.values()):
            raise ValueError("Exactly four callable voices are required")
        if not callable(validator) or not callable(assessor):
            raise ValueError("Validator and assessor must be callable")
        if any(validator is voice for voice in voices.values()):
            raise ValueError("Validator must be independent of the four voices")
        if type(max_revisions) is not int or not 0 <= max_revisions <= 2:
            raise ValueError("max_revisions must be between 0 and 2")
        if type(source_first_selection) is not bool:
            raise ValueError("source_first_selection must be a boolean")
        self.source_first_selection = source_first_selection
        if policy_corrections is not None and (
            not isinstance(policy_corrections, Mapping) or any(
                type(number) is not int or number < 1 or not isinstance(reason, str) or not reason.strip()
                for number, reason in policy_corrections.items())
        ):
            raise ValueError("policy_corrections requires positive entry numbers and nonempty diagnostic reasons")
        self.path = Path(path)
        self.voices = dict(voices)
        self.validator, self.assessor = validator, assessor
        self.max_revisions = max_revisions
        self.policy_corrections = dict(policy_corrections or {})
        if final_review is not None and not callable(final_review):
            raise ValueError("Final reviewer must be callable")
        if draft_overrides and final_review is None:
            raise ValueError("Corrected revisions require the versioned independent reviewer")
        if editorial_additions is not None and (
                not isinstance(editorial_additions, Mapping) or any(
                    type(n) is not int or n < 1 or not isinstance(value, dict) or
                    set(value) != {"seed_sha256", "paragraph_mr"} or
                    not isinstance(value["seed_sha256"], str) or
                    re.fullmatch(r"[0-9a-f]{64}", value["seed_sha256"]) is None or
                    not isinstance(value["paragraph_mr"], str) or not value["paragraph_mr"].strip()
                    for n, value in editorial_additions.items())):
            raise ValueError("Editorial additions require numbered seed hashes and paragraphs")
        if editorial_additions and final_review is None:
            raise ValueError("Editorial additions require the versioned independent reviewer")
        self.final_review = final_review
        self.draft_overrides = deepcopy(dict(draft_overrides or {}))
        self.editorial_additions = deepcopy(dict(editorial_additions or {}))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS research_runs (
                    number INTEGER PRIMARY KEY, request_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_stages (
                    number INTEGER NOT NULL, stage TEXT NOT NULL, speaker TEXT NOT NULL,
                    request_hash TEXT NOT NULL, response_json TEXT NOT NULL,
                    PRIMARY KEY (number, stage, speaker));
                CREATE TABLE IF NOT EXISTS research_attempts (
                    number INTEGER NOT NULL, stage TEXT NOT NULL, speaker TEXT NOT NULL,
                    attempt INTEGER NOT NULL, request_hash TEXT NOT NULL,
                    state TEXT NOT NULL, response_json TEXT, error TEXT,
                    PRIMARY KEY (number, stage, speaker, attempt));
                CREATE TABLE IF NOT EXISTS research_reconsiderations (
                    number INTEGER PRIMARY KEY, revision INTEGER NOT NULL);
            """)
            db.execute(_RETRY_AUTHORIZATION_SCHEMA)
            db.execute("CREATE TABLE IF NOT EXISTS research_v2_lineage (number INTEGER PRIMARY KEY, seed_hash TEXT NOT NULL)")

    def authorize_schema_retry(self, number: int, stage: str, speaker: str, reason: str) -> dict:
        """Purpose: authorize narrow recovery in this instance's checkpoint file.

        Parameters: number, stage, speaker and audit reason. Returns: authorization
        record from the public path helper. Failures: identical eligibility/SQLite
        errors; use the separate batch path and number 0 for a batch-stage failure.
        """
        return authorize_schema_retry(self.path, number, stage, speaker, reason)

    def _bind(self, number: int, base: dict) -> None:
        """Purpose: reject stale runs before callbacks. Parameters: number, base.

        Returns: None after atomic input registration. Failures: ValueError for
        changed inputs or revision policy; SQLite errors propagate.
        """
        digest = hashlib.sha256(_json({**base, "max_revisions": self.max_revisions,
                                      "protocol": PROTOCOL_VERSION}).encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT request_hash FROM research_runs WHERE number=?",
                             (number,)).fetchone()
            if row and row[0] != digest:
                raise ValueError(f"Stale inputs for research entry {number}")
            db.execute("INSERT OR IGNORE INTO research_runs VALUES (?,?)", (number, digest))

    def _stage(self, request: dict, callback: Callable, *, attempt_limit: int = 2) -> dict:
        """Purpose: execute/reuse one durable stage with two normal schema attempts.

        Parameters: request, complete payload; callback, parent callable;
        attempt_limit, 1 for a single reconsideration call or the default 2. Returns:
        a validated response including extra metadata. Failures: ValueError for
        stale requests, exhausted failures, or unresolved in-flight calls; SQLite
        errors propagate. Every returned response/exception is recorded first.
        A matching one-time authorization permits exactly a third attempt only
        for ordinary two-attempt stages, never for a one-call reconsideration.
        """
        if type(attempt_limit) is not int or attempt_limit not in (1, 2):
            raise ValueError("Stage attempt_limit must be 1 or 2")
        request = deepcopy(request)
        number, stage, speaker = (request[key] for key in ("number", "stage", "speaker"))
        key = (number, stage, speaker)
        digest = hashlib.sha256(_json(request).encode()).hexdigest()
        while True:
            with sqlite3.connect(self.path) as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT request_hash,response_json FROM research_stages "
                                 "WHERE number=? AND stage=? AND speaker=?", key).fetchone()
                if row:
                    if row[0] != digest:
                        raise ValueError(f"Stale request at {stage}/{speaker}")
                    saved = json.loads(row[1])
                    if stage == 'proposal' and speaker == 'sutrakar':
                        from src.orchestration.source_first_proposal_recovery import verify_cached_stage
                        verify_cached_stage(self.path, db, key, digest, saved)
                    if 'partial_stage_completion' in saved:
                        from src.orchestration.source_first_partial_completion import verify_receipt
                        pointer = saved['partial_stage_completion']
                        receipt, merged = verify_receipt(pointer['path'], pointer['sha256'])
                        if (receipt['plan']['core_request_sha256'] != digest
                                or saved != {**merged, 'partial_stage_completion': pointer}):
                            raise ValueError('Composite council-stage adoption changed')
                    if stage == 'peer_review' and speaker == 'researcher':
                        from src.orchestration.source_first_evidence_anchor import verify_cached_stage
                        verify_cached_stage(self.path, db, key, digest, saved)
                    if request.get('source_peer_policy') is not None and stage == 'peer_review':
                        from src.orchestration.source_peer_evidence import verify_cached
                        verify_cached(self.path, request, saved)
                    return _check_answer(stage, speaker, saved, request)
                if stage == 'proposal' and speaker == 'sutrakar':
                    from src.orchestration.source_first_proposal_recovery import require_adopted_known_stage
                    require_adopted_known_stage(digest)
                attempts = db.execute(
                    "SELECT request_hash,state,response_json,error FROM research_attempts "
                    "WHERE number=? AND stage=? AND speaker=? ORDER BY attempt", key).fetchall()
                if any(row[0] != digest for row in attempts):
                    raise ValueError(f"Stale failed request at {stage}/{speaker}")
                if any(row[1] == "RUNNING" for row in attempts):
                    raise ValueError(f"Unresolved in-flight stage {stage}/{speaker}")
                if any(row[1] == "HARD_FAILED" for row in attempts):
                    raise ValueError(f"Terminal callback failure at {stage}/{speaker}: {attempts[-1][3]}")
                authorization = db.execute("SELECT request_hash FROM research_schema_retry_authorizations "
                                           "WHERE number=? AND stage=? AND speaker=?", key).fetchone()
                if authorization and authorization[0] != digest:
                    raise ValueError(f"Stale schema retry authorization at {stage}/{speaker}")
                max_attempts = 3 if authorization and attempt_limit == 2 else attempt_limit
                if len(attempts) >= max_attempts:
                    raise ValueError(f"Exhausted {stage}/{speaker}: {attempts[-1][3]}")
                attempt = len(attempts) + 1
                db.execute("INSERT INTO research_attempts VALUES (?,?,?,?,?,'RUNNING',NULL,NULL)",
                           (*key, attempt, digest))
            payload = deepcopy(request)
            if attempts:
                payload.update(repair_feedback=attempts[-1][3],
                               previous_invalid_response=json.loads(attempts[-1][2]),
                               instruction="Correct the schema error; return a complete dictionary. "
                                           "Review only literal evidence in the current target.")
            raw = None
            answer = None
            error = None
            fatal = None
            try:
                raw = callback(payload)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                if not isinstance(exc, ValueError):
                    fatal = exc
            if error is None:
                try:
                    # Freeze returned objects before validating or checkpointing.
                    current = deepcopy(raw)
                    if request.get('source_peer_policy') is not None and stage == 'peer_review':
                        from src.orchestration.source_peer_evidence import materialize_stage
                        current = materialize_stage(self.path, request, payload, current, attempt)
                    answer = _check_answer(stage, speaker, current, request)
                except (ValueError, TypeError) as exc:
                    error = f"{type(exc).__name__}: {exc}"
            try:
                serialized = _json(raw)
            except (TypeError, ValueError):
                serialized = _json({"invalid_response_repr": repr(raw)})
            with sqlite3.connect(self.path) as db:
                db.execute("UPDATE research_attempts SET state=?,response_json=?,error=? "
                           "WHERE number=? AND stage=? AND speaker=? AND attempt=?",
                           ("HARD_FAILED" if fatal else "FAILED" if error else "COMPLETE",
                            serialized, error, *key, attempt))
                if error is None:
                    db.execute("INSERT INTO research_stages VALUES (?,?,?,?,?)",
                               (*key, digest, _json(answer)))
            if fatal is not None:
                raise fatal
            if error is None:
                return answer

    def _parallel(self, base: dict, stage: str, speakers: tuple[str, ...],
                  **context: dict) -> dict:
        """Purpose: run one round behind a barrier. Parameters: base, stage,
        speakers, and context. Returns: role-keyed validated records. Failures:
        stage exceptions propagate after all ready sibling outputs are saved.
        """
        def turn(speaker: str) -> tuple[str, dict]:
            """Purpose: dispatch a role. Parameters: speaker. Returns: role/answer.
            Failures: durable stage errors propagate to the round barrier.
            """
            request = {**base, **context, "stage": stage, "speaker": speaker}
            return speaker, self._stage(request, self.voices[speaker])

        with ThreadPoolExecutor(max_workers=len(speakers)) as pool:
            return dict(pool.map(turn, speakers))

    def _assess(self, payload: dict) -> dict:
        """Purpose: adapt assessor signature. Parameters: isolated stage payload.

        Returns: assessor(entry, sources, prior, forbidden, used) dictionary.
        Failures: callback exceptions are persisted by _stage; mutations affect
        only this payload, never the saved draft or caller-owned input objects.
        """
        return self.assessor(payload["draft"], payload["sources"],
                             payload["prior_formulas"], payload["forbidden_originals"],
                             set(payload["used_case_ids"]))

    def _entry_base(self, number: int, brief: dict, sources: dict,
                    prior_formulas: list[str], forbidden_originals: list[str],
                    used_case_ids: set[str]) -> dict:
        """Purpose: validate/copy entry inputs. Parameters: number, brief, sources,
        prior_formulas, forbidden_originals, used_case_ids. Returns: JSON payload.
        Failures: ValueError for malformed inputs; no arbitrary upper count cap.
        """
        if type(number) is not int or number < 1:
            raise ValueError("Research entry number must be a positive integer")
        if not isinstance(brief, dict) or not isinstance(sources, dict):
            raise ValueError("brief and sources must be dictionaries")
        if any(not isinstance(values, list) or any(not isinstance(v, str) for v in values)
               for values in (prior_formulas, forbidden_originals)):
            raise ValueError("Prior formulas and forbidden originals must be string lists")
        if not isinstance(used_case_ids, set) or any(not isinstance(v, str) for v in used_case_ids):
            raise ValueError("used_case_ids must be a set of strings")
        return deepcopy({"number": number, "brief": brief, "sources": sources,
                         "prior_formulas": prior_formulas, "forbidden_originals": forbidden_originals,
                         "used_case_ids": sorted(used_case_ids)})

    def _deliberate(self, base: dict) -> dict:
        """Purpose: conduct sixteen discussion calls once. Parameters: base payload.
        Returns: discussion, proposal, peer_review. Failures: durable schema or
        callback errors; stage checkpoints retain completed siblings and usage.
        """
        discussion = {}
        for stage in ("position", "challenge", "reply"):
            discussion[stage] = self._parallel(base, stage, VOICES, discussion=discussion)
        context = {**base, "discussion": discussion, "speaker": "sutrakar"}
        proposal = self._stage({**context, "stage": "proposal"}, self.voices["sutrakar"])
        peer_review = self._parallel(base, "peer_review", VOICES[:-1],
                                     discussion=discussion, proposal=proposal)
        return {"discussion": discussion, "proposal": proposal, "peer_review": peer_review}

    def run_batch_discussion(self, batch_id: str | int, briefs: list,
                             sources_by_entry: dict, prior_formulas: list[str],
                             forbidden_originals: list[str], *, source_peer_policy=None) -> dict:
        """Purpose: share four-voice deliberation across related planned entries.

        Parameters: batch_id, nonempty string or positive integer; briefs, nonempty
        list of distinct positive numbered brief dictionaries; sources_by_entry,
        exact number-keyed source packets (integer or decimal string keys);
        prior_formulas/forbidden_originals, frozen batch-start exclusions.
        Returns: batch_id, checkpoint_path, discussion, proposal, peer_review.
        Every batch uses a separate sibling SQLite file named with its ID hash.
        No composition, assessor, or validator call occurs here.

        Payloads retain stage/speaker/number/brief/sources/discussion and add
        scope='batch', batch_id, briefs, entry_numbers, sources_by_entry. number=0
        is an internal batch checkpoint marker, never a generated entry number.
        Response schemas: positions={number-string: substantive record}; challenges
        and answers={other-role: {number-string: substantive record}}; proposal
        has proposals=[{number,proposed_sutra,derivation,selected_source_ids}];
        peers return reviews=[{number,verdict,issues}]. Review issue field paths
        address that entry's proposal (e.g. proposed_sutra), not the outer array.
        Failures: ValueError for bad coverage/inputs/stale checkpoints; callback
        hard failures propagate once. All short proposals gate peer review.

        Opt-in source_first_selection=True: every packet includes
        source_pair_ids=["N23", "S8"] and references=[{id: "N23", ...}, ...].
        Proposals additionally require decision="ACCEPT" or decision="REJECT".
        ACCEPT keeps all legacy fields and selects both pair IDs; REJECT omits
        proposed_sutra and supplies rejection_reason (at least five words).
        Peers review either disposition using the existing grounded issue schema
        (e.g. field="rejection_reason"). Returns accepted_numbers/rejected_numbers
        only in this mode. Caller composes accepted numbers and skips rejected
        numbers; a peer objection remains recorded, never forces a formula or
        silently converts a rejection. Resume reuses every completed round.
        Optional source_peer_policy is bound only when supplied for an unstarted
        future batch; default base/request bytes stay unchanged. Peer raw IDs are
        materialized before the same validators, and exact-copy holds are per entry.
        """
        if not ((isinstance(batch_id, str) and batch_id.strip()) or
                (type(batch_id) is int and batch_id > 0)):
            raise ValueError("batch_id must be a nonempty string or positive integer")
        if not isinstance(briefs, list) or not briefs:
            raise ValueError("Batch requires a nonempty briefs list")
        if any(not isinstance(b, dict) or type(b.get("number")) is not int or
               b["number"] < 1 for b in briefs):
            raise ValueError("Every batch brief requires a positive integer number")
        numbers = [brief["number"] for brief in briefs]
        _numbered(briefs, numbers, "Batch briefs")
        if not isinstance(sources_by_entry, dict):
            raise ValueError("sources_by_entry must be an exact number-keyed dictionary")
        packets = {}
        for key, packet in sources_by_entry.items():
            if not ((type(key) is int and key > 0) or
                    (isinstance(key, str) and key in {str(n) for n in numbers})):
                raise ValueError("Invalid sources_by_entry key")
            if str(key) in packets or not isinstance(packet, dict):
                raise ValueError("Duplicate source key or malformed source packet")
            packets[str(key)] = packet
        if set(packets) != {str(n) for n in numbers}:
            raise ValueError("sources_by_entry requires exact entry numbers")
        # Reuse entry input validation for both complete exclusion lists.
        self._entry_base(numbers[0], briefs[0], packets[str(numbers[0])],
                         prior_formulas, forbidden_originals, set())
        base = deepcopy({"number": 0, "brief": {"batch_id": batch_id}, "sources": packets,
                         "scope": "batch", "batch_id": batch_id, "briefs": briefs,
                         "entry_numbers": numbers, "sources_by_entry": packets,
                         "prior_formulas": prior_formulas, "forbidden_originals": forbidden_originals,
                         "used_case_ids": []})
        if self.source_first_selection:
            for packet in packets.values():
                _source_pair_ids(packet)
            base["source_first_selection"] = SOURCE_FIRST_SELECTION
        if source_peer_policy is not None:
            from src.orchestration.source_peer_evidence import validate_policy
            if not self.source_first_selection:
                raise ValueError('Peer evidence policy requires source-only selection')
            base['source_peer_policy'] = deepcopy(validate_policy(source_peer_policy, numbers))
        digest = hashlib.sha256(_json(batch_id).encode()).hexdigest()
        batch_path = self.path.with_name(f"{self.path.name}.batch-{digest}.sqlite3")
        batch = ResearchCouncil(batch_path, self.voices, self.validator, self.assessor, self.max_revisions,
                                source_first_selection=self.source_first_selection)
        batch._bind(0, base)
        result = batch._deliberate(base)
        result["discussion"]["_batch"] = {
            "batch_id": batch_id, "entry_numbers": numbers,
            "prior_formulas": deepcopy(prior_formulas),
            "forbidden_originals": deepcopy(forbidden_originals),
            "entry_hashes": {str(b["number"]): hashlib.sha256(_json({
                "brief": b, "sources": packets[str(b["number"])]}).encode()).hexdigest() for b in briefs},
        }
        if source_peer_policy is not None:
            from src.orchestration.source_peer_evidence import literal_constraints
            result['discussion']['_batch']['source_peer_policy'] = deepcopy(source_peer_policy)
            result['server_constraints'] = literal_constraints(result['proposal'], prior_formulas, forbidden_originals, source_peer_policy)
        if self.source_first_selection:
            result["discussion"]["_batch"]["source_first_selection"] = SOURCE_FIRST_SELECTION
            proposals = _numbered(result["proposal"]["proposals"], numbers, "Batch proposals")
            result["accepted_numbers"] = [n for n in numbers if proposals[n]["decision"] == "ACCEPT"]
            result["rejected_numbers"] = [n for n in numbers if proposals[n]["decision"] == "REJECT"]
        return {"batch_id": batch_id, "checkpoint_path": str(batch_path.resolve()), **result}

    def compose_entry(self, number: int, brief: dict, sources: dict,
                      prior_formulas: list[str], forbidden_originals: list[str],
                      used_case_ids: set[str], discussion: dict, proposal: dict,
                      peer_review: dict, *, case_capsule: dict | None = None) -> dict:
        """Purpose: compose/review one entry from existing deliberation, never rerun it.

        Parameters: positive number, brief, sources, complete current exclusions,
        used_case_ids, discussion, proposal and three-role peer_review. Batch
        callers may pass full batch proposal/reviews or select this numbered
        proposal and its three reviews; keep discussion's _batch binding intact.
        Current prior_formulas must extend the frozen batch-start history.
        Returns: draft/review/assessment/discussion/proposal/peer_review/revisions
        and READY_FOR_AUTHOR_REVIEW or NEEDS_REVIEW. Cases/usage remain intact.
        Failures: ValueError for stale, mismatched or malformed deliberation;
        callback hard failures propagate, schema failures get at most two tries.
        In opt-in source-first mode, keep the batch policy binding intact and
        pass only accepted entries. Rejected entries raise before any composition,
        assessor or validator callback; discussion checkpoints remain reusable.
        Optional case_capsule is source-first only. Build it with
        source_first_case_capsule.build_case_capsule; pass the ORIGINAL empty-case
        sources here. After all original bindings/rounds pass, only cases and
        capsule provenance are added. Composition, assessment and reviewer
        callbacks receive composition_binding; adapters must retain that binding
        in provider/cache identity (see the capsule module's integration recipe).
        No capsule leaves legacy payloads and checkpoint hashes unchanged.
        """
        base = self._entry_base(number, brief, sources, prior_formulas,
                                forbidden_originals, used_case_ids)
        if not all(isinstance(v, dict) for v in (discussion, proposal, peer_review)):
            raise ValueError("Composition requires discussion, proposal and peer-review dictionaries")
        discussion, proposal, peer_review = deepcopy((discussion, proposal, peer_review))
        binding = discussion.get("_batch")
        expected_policy = SOURCE_FIRST_SELECTION if self.source_first_selection else None
        if ((binding.get("source_first_selection") if isinstance(binding, dict) else None)
                != expected_policy or (self.source_first_selection and binding is None)):
            raise ValueError("Batch source-first selection policy mismatch")
        if binding is not None:
            if not isinstance(binding, dict) or number not in binding.get("entry_numbers", []):
                raise ValueError("Entry absent from batch discussion")
            digest = hashlib.sha256(_json({"brief": brief, "sources": sources}).encode()).hexdigest()
            if binding.get("entry_hashes", {}).get(str(number)) != digest:
                raise ValueError("Entry brief/sources changed since batch discussion")
            previous = binding.get("prior_formulas")
            if not isinstance(previous, list) or prior_formulas[:len(previous)] != previous or \
                    binding.get("forbidden_originals") != forbidden_originals:
                raise ValueError("Entry exclusions disagree with batch discussion")
            round_request = {"scope": "batch", "entry_numbers": binding["entry_numbers"]}
            if "proposals" in proposal:
                if not self.source_first_selection:
                    _check_answer("proposal", "sutrakar", proposal, round_request)
                proposal = _numbered(proposal["proposals"], binding["entry_numbers"], "Batch proposals")[number]
            selected_request = {"scope": "batch", "entry_numbers": [number]}
            if self.source_first_selection:
                selected_request.update(source_first_selection=SOURCE_FIRST_SELECTION,
                                        sources_by_entry={str(number): sources})
            _check_answer("proposal", "sutrakar", {"proposals": [proposal]},
                          selected_request)
            if self.source_first_selection and proposal["decision"] == "REJECT":
                raise ValueError("Rejected source-first entry: skip composition; retain discussion")
            for role, review in list(peer_review.items()):
                if isinstance(review, dict) and "reviews" in review:
                    peer_review[role] = _numbered(review["reviews"], binding["entry_numbers"], "Batch reviews")[number]
                if not isinstance(peer_review[role], dict) or peer_review[role].get("number") != number:
                    raise ValueError("Peer review number does not match the entry")
        else:
            round_request = base
            if "number" in proposal and proposal["number"] != number:
                raise ValueError("Proposal number does not match the entry")
            _check_answer("proposal", "sutrakar", proposal, base)
        for stage in ("position", "challenge", "reply"):
            records = discussion.get(stage)
            if not isinstance(records, dict) or set(records) != set(VOICES):
                raise ValueError("Composition requires all four voices in every discussion round")
            for role, answer in records.items():
                _check_answer(stage, role, answer, round_request)
        if set(peer_review) != set(VOICES[:-1]):
            raise ValueError("Composition requires exactly three peer reviews")
        for role, review in peer_review.items():
            _check_answer("peer_review", role, review, {"proposal": proposal})
        if case_capsule is not None:
            if not self.source_first_selection:
                raise ValueError("Case capsule requires source-first selection")
            from src.orchestration.source_first_case_capsule import apply_case_capsule
            base["sources"], base["composition_binding"] = apply_case_capsule(
                case_capsule, number=number, brief=brief, sources=sources,
                discussion=discussion, proposal=proposal, peer_review=peer_review,
                used_case_ids=used_case_ids)
        self._bind(number, {**base, "mode": "compose_entry", "discussion": discussion,
                            "proposal": proposal, "peer_review": peer_review})
        return self._compose(base, discussion, proposal, peer_review)

    def run(self, number: int, brief: dict, sources: dict,
            prior_formulas: list[str], forbidden_originals: list[str],
            used_case_ids: set[str]) -> dict:
        """Purpose: preserve the single-entry protocol with unlimited positive numbering.

        Parameters: number, brief, sources, prior_formulas, forbidden_originals,
        used_case_ids. Returns: same unapproved result contract as compose_entry.
        Failures: stale inputs/schema failures raise ValueError; hard callback
        errors propagate. Parent controls planned count; two repairs maximum.
        Opt-in selection uses run_batch_discussion followed by compose_entry;
        this legacy single-entry convenience method does not select/reject.
        """
        if self.source_first_selection:
            raise ValueError("Source-first selection requires run_batch_discussion")
        base = self._entry_base(number, brief, sources, prior_formulas,
                                forbidden_originals, used_case_ids)
        self._bind(number, {**base, "mode": "run"})
        return self._compose(base, **self._deliberate(base))

    def _compose(self, base: dict, discussion: dict, proposal: dict, peer_review: dict) -> dict:
        """Purpose: reuse bounded composition/assessment/independent-review cycles.

        Parameters: validated base and deliberation records. Returns: exact final
        draft, reviews and repair count, never approval. Failures: durable stage
        errors propagate; quality failures return NEEDS_REVIEW after the budget.
        Each independent review receives selected peers' role/reason/severity
        only, never old proposal quotes. Resolved concerns do not block PASS.
        Returns review_history with stage/revision/review records. One durable
        validator-only reconsideration may avoid a repair; saved later drafts
        always take precedence over reconsidering an obsolete draft.
        """
        if self.final_review is not None:
            return self._compose_current_review(base, discussion, proposal, peer_review)
        context = {**base, "discussion": discussion, "speaker": "sutrakar"}
        composition = {**context, "proposal": proposal, "peer_review": peer_review}
        peer_concerns = [{"role": role, "reason": issue["reason"], "severity": issue["severity"]}
                         for role in VOICES[:-1] for issue in peer_review[role]["issues"]]
        review_history = []
        with sqlite3.connect(self.path) as db:
            saved_stages = db.execute("SELECT stage FROM research_stages WHERE number=? AND speaker='sutrakar'",
                                      (base["number"],)).fetchall()
        latest_saved_revision = max((int(match.group(1) or 0) for (stage,) in saved_stages
                                     if (match := re.fullmatch(r"composition(?:_(\d+))?", stage))), default=-1)
        for revision in range(self.max_revisions + 1):
            suffix = f"_{revision}" if revision else ""
            draft = self._stage({**composition, "stage": f"composition{suffix}"},
                                self.voices["sutrakar"])
            # Preserve reasons to check without presenting abandoned wording as
            # evidence. Only the current draft may support a new review issue.
            current = {**base, "discussion": {}, "draft": draft}
            assessment = self._stage({**current, "stage": f"assessment{suffix}",
                                      "speaker": "assessor"}, self._assess)
            review = self._stage({**current, "stage": f"independent_review{suffix}",
                                  "speaker": "validator", "peer_concerns": peer_concerns,
                                  "review_instruction": "Assess whether the CURRENT draft resolves each "
                                      "peer concern. Resolved concerns may PASS. Cite only literal text "
                                      "in the current draft for any remaining issue; do not edit the draft "
                                      "or treat an obsolete proposal objection as an automatic failure."},
                                 self.validator)
            review_history.append({"stage": f"independent_review{suffix}",
                                   "revision": revision, "review": deepcopy(review)})
            reconsidered = self._reconsider_review(
                current, revision, review, assessment, peer_concerns,
                has_later_composition=latest_saved_revision > revision)
            if reconsidered is not None:
                review = reconsidered
                review_history.append({"stage": "independent_review_reconsideration",
                                       "revision": revision, "review": deepcopy(review)})
            ready = assessment["status"] == "PASS" and review["verdict"] == "PASS"
            if (ready and latest_saved_revision <= revision) or revision == self.max_revisions:
                corrected = self._correct_review_policy(current, revision, review, assessment, peer_concerns)
                if corrected is not None:
                    review = corrected
                    review_history.append({"stage": "independent_review_policy_correction_v1",
                                           "revision": revision, "review": deepcopy(review)})
                    ready = assessment["status"] == "PASS" and review["verdict"] == "PASS"
                return {"draft": draft, "review": review, "assessment": assessment,
                        "discussion": discussion, "proposal": proposal,
                        "peer_review": peer_review, "revisions": revision,
                        "review_history": review_history,
                        "status": "READY_FOR_AUTHOR_REVIEW" if ready else "NEEDS_REVIEW"}
            # Only validated current-draft review issues reach repair. Historical
            # proposal criticism is deliberately omitted from repair payloads.
            composition = {**context, "draft": draft, "review": review,
                           "assessment": assessment, "revision": revision + 1}

    def _compose_current_review(self, base, discussion, proposal, peer_review):
        """Reuse paid composition and review the exact latest editorial revision.

        Parameters are canonical base and saved four-voice discussion/proposal.
        Returns a result compatible with export; raw legacy stages stay intact.
        One v2 repair is available for substantiated content defects, never for
        uncertain or invalid reviews. Failures propagate and stop paid work.
        The reviewer owns its full prompt/model/source-bound cache. Inspect its
        key and the retained draft hash when diagnosing a changed verdict.
        """
        context = {**base, "discussion": discussion, "speaker": "sutrakar"}
        with sqlite3.connect(self.path) as db:
            rows = dict(db.execute("SELECT stage,response_json FROM research_stages WHERE number=? AND speaker='sutrakar'",
                                   (base["number"],)).fetchall())
        repaired = "composition_v2_1" in rows
        if base["number"] in self.draft_overrides:
            draft = deepcopy(self.draft_overrides[base["number"]])
        else:
            old = [(int(m.group(1) or 0), value) for key, value in rows.items()
                   if (m := re.fullmatch(r"composition(?:_(\d+))?", key))]
            if old:
                draft = json.loads(max(old)[1])
            else:
                draft = self._stage({**context, "proposal": proposal, "peer_review": peer_review,
                                     "stage": "composition"}, self.voices["sutrakar"])
        seed_hash = hashlib.sha256(_json(draft).encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            lineage = db.execute("SELECT seed_hash FROM research_v2_lineage WHERE number=?",
                                 (base["number"],)).fetchone()
            if lineage and lineage[0] != seed_hash:
                raise ValueError("Changed v2 composition seed; saved repair cannot replace a newer correction")
            if repaired and not lineage:
                raise ValueError("Saved v2 repair has no verified seed lineage")
            db.execute("INSERT OR IGNORE INTO research_v2_lineage VALUES (?,?)",
                       (base["number"], seed_hash))
        if repaired:
            draft = json.loads(rows["composition_v2_1"])
        draft = _check_answer("composition", "sutrakar", draft, base)
        editorial = None
        addition = self.editorial_additions.get(base["number"])
        if addition and not repaired:
            if addition["seed_sha256"] != seed_hash:
                raise ValueError("Editorial addition seed hash differs from original composition")
            original_words = sum(_devanagari_word(token) for paragraph in draft["exposition"]
                                 for token in paragraph.split())
            paragraph = addition["paragraph_mr"]
            added_words = sum(_devanagari_word(token) for token in paragraph.split())
            if not 450 <= original_words < 500 or added_words < 20 or original_words + added_words < 500:
                raise ValueError("Editorial addition requires 450-499 original words, at least 20 added words and 500 total")
            draft = deepcopy(draft)
            draft["exposition"].insert(len(draft["exposition"]) - 1, paragraph)
            editorial = {"provenance": "local_editorial", "seed_sha256": seed_hash,
                         "paragraph_sha256": hashlib.sha256(paragraph.encode()).hexdigest(),
                         "draft_sha256": hashlib.sha256(_json(draft).encode()).hexdigest(),
                         "original_words": original_words, "added_words": added_words,
                         "provider_calls": 0, "applied_before_revision": 0}
        history = []
        repair_limit = min(self.max_revisions, 1)
        for revision in range(int(repaired), repair_limit + 1):
            current = {**base, "draft": draft, "discussion": {}}
            assessment = self._assess(current)
            review = self.final_review(current)
            if review.get("outcome") not in {"READY", "REVISION_REQUIRED", "AUTHOR_REVIEW"}:
                raise RuntimeError("Versioned reviewer returned no typed disposition")
            if (review["outcome"] == "READY") != (review.get("verdict") == "PASS"):
                raise RuntimeError("Versioned review outcome and export verdict disagree")
            history.append({"stage": "independent_review_v2", "revision": revision,
                            "review": deepcopy(review)})
            ready = assessment["status"] == "PASS" and review["verdict"] == "PASS"
            if ready or revision == repair_limit or review["outcome"] == "AUTHOR_REVIEW":
                result = {"draft": draft, "assessment": assessment, "review": review,
                        "discussion": discussion, "proposal": proposal, "peer_review": peer_review,
                        "revisions": revision, "review_history": history,
                        "status": "READY_FOR_AUTHOR_REVIEW" if ready else "NEEDS_REVIEW"}
                if editorial:
                    result["editorial_addition"] = editorial
                return result
            draft = self._stage({**context, "draft": draft, "review": review,
                                 "assessment": assessment, "revision": 1,
                                 "stage": "composition_v2_1"}, self.voices["sutrakar"])

    def _reconsider_review(self, current: dict, revision: int, review: dict,
                           assessment: dict, peer_concerns: list,
                           *, has_later_composition: bool) -> dict | None:
        """Purpose: allow one cheaper, independent reconsideration per entry.

        Parameters: current draft payload, revision, original review, assessment,
        selected peer_concerns, and whether a newer composition is already saved.
        Returns: validated reconsideration, cached if available, or None if not
        eligible/already assigned to another revision. Original review rows are
        untouched. Failures: schema/provider errors persist after one callback;
        unresolved or missing obsolete checkpoints fail closed without replay.
        """
        number = current["number"]
        stage = "independent_review_reconsideration"
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            assigned = db.execute("SELECT revision FROM research_reconsiderations WHERE number=?",
                                  (number,)).fetchone()
            if assigned is None:
                if has_later_composition or assessment["status"] != "PASS" or review["verdict"] != "REVIEW_REQUIRED":
                    return None
                db.execute("INSERT INTO research_reconsiderations VALUES (?,?)", (number, revision))
            elif assigned[0] != revision:
                return None
            if has_later_composition and not db.execute(
                "SELECT 1 FROM research_stages WHERE number=? AND stage=? AND speaker='validator'",
                (number, stage),
            ).fetchone():
                raise ValueError("Missing obsolete reconsideration checkpoint; refusing validator replay")
        request = {**current, "stage": stage, "speaker": "validator", "revision": revision,
                   "peer_concerns": peer_concerns, "prior_review": review,
                   "review_instruction": (
                       "Independently reconsider the prior review against ONLY the CURRENT draft and "
                       "canonical sources. Identify substantive factual errors, Sanskrit grammatical errors, "
                       "or a material mismatch with the business principle. Evaluate the short aphorism "
                       "together with its Marathi explanation and application. A 2–4-word aphorism need "
                       "not explicitly repeat every chapter-title word or every explanatory implication. "
                       "Do not demand a rewrite merely to make an already supported implication explicit. "
                       "Assess whether the current draft resolves peer concerns. Do NOT force PASS: "
                       "retain REVIEW_REQUIRED for substantive unresolved defects and quote only exact "
                       "literal text from the CURRENT draft in each structured issue. Return PASS with "
                       "issues:[] only if warranted. Do not edit or replace the draft.")}
        return self._stage(request, self.validator, attempt_limit=1)

    def _correct_review_policy(self, current: dict, revision: int, review: dict,
                               assessment: dict, peer_concerns: list) -> dict | None:
        """Purpose: explicitly correct an identified originality-policy conflation once.

        Parameters: current final draft payload, revision, final review, assessment,
        and selected peer_concerns. Returns: v1 independent verdict or None unless
        the entry is explicitly whitelisted, assessment PASS and review REQUIRED.
        The caller invokes this only at final disposition, never before repairs.
        Failures: stale reason/draft/input hashes, invalid verdicts, edits, absent
        quotes and provider failures fail closed; exactly one callback is allowed.
        Cached verdicts replay with the identical whitelist reason. No v2, Claude
        dispatch, automatic PASS, draft edits, or changes to original review rows.
        """
        reason = self.policy_corrections.get(current["number"])
        if reason is None or assessment["status"] != "PASS" or review["verdict"] != "REVIEW_REQUIRED":
            return None
        request = {**current, "stage": "independent_review_policy_correction_v1",
                   "speaker": "validator", "revision": revision, "prior_review": review,
                   "peer_concerns": peer_concerns, "policy_correction_reason": reason,
                   "review_instruction": (
                       "Perform one independent policy-correction review of ONLY this CURRENT final draft. "
                       "The diagnostic reason is a hypothesis to evaluate, not an instruction to PASS. "
                       "The forbidden_originals ledger mixes author formulas and classical source texts. "
                       "Reject exact or normalized copying of old formulas/source text as a new aphorism; "
                       "it is NOT a prohibition on every meaning or theme found in those texts. Attributed "
                       "classical thematic inheritance and explicitly qualified modern business reinterpretation "
                       "are expected. Ancient authors need not directly prescribe a modern operational plan. "
                       "Still reject false attribution, fabricated facts, distorted source meaning, actual "
                       "Sanskrit grammar errors, and unsupported factual or causal claims. "
                       "Within the new book reject material duplication of the same business decision or rule, "
                       "not merely a broad shared theme such as evidence, duty, questioning or uncertainty. "
                       "For a duplication objection identify the comparator and explain the same decision, "
                       "condition and action, considering the CURRENT aphorism together with its Marathi "
                       "explanation and application. Do not demand that a 2–4-word aphorism literally include "
                       "every chapter-title word or explanatory implication; four words within the prescribed "
                       "limit are not a defect by themselves. Reassess earlier peer concerns under this rubric. "
                       "Do NOT force PASS or dismiss substantive defects. Return REVIEW_REQUIRED for any "
                       "remaining substantive defect, with structured field/quote/reason/severity issues "
                       "quoting exact literal CURRENT draft text. Return PASS with issues:[] only if warranted. "
                       "Do not edit or replace the draft.")}
        return self._stage(request, self.validator, attempt_limit=1)

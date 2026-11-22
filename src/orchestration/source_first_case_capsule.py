"""Offline, opt-in case attachment AFTER an accepted source-only discussion.

All three selected peer reviews must be PASS with empty issues. A held peer
review blocks capsule construction/application before cases or callbacks.

Construction (no model/credential/SDK imports or calls)::

    capsule = build_case_capsule(
        number=n, brief=original_brief, sources=original_sources,
        discussion=batch['discussion'], proposal=batch['proposal'],
        peer_review=batch['peer_review'], case_work_dir=new_work,
        case_slots=[{'kind': 'positive', 'case_id': positive_id,
                     'fit_reason_mr': fit, 'limitations_mr': limits},
                    {'kind': 'caution', 'case_id': caution_id,
                     'fit_reason_mr': fit2, 'limitations_mr': limits2}],
        used_case_ids=used_ids, used_identity_keys=historical_reserved_keys)
    # Save this returned JSON capsule in the caller's NEW work directory.
    council.compose_entry(n, original_brief, original_sources, prior, forbidden,
                          used_ids, batch['discussion'], batch['proposal'],
                          batch['peer_review'], case_capsule=capsule)

The default overlay filename is business-case-verification-overlay-complete.json.
All inputs are read-only. Exact UTF-8 bytes of the pool, complete overlay and
every input proof are embedded and hashed. Replay uses a disposable temporary
directory and the EXISTING merge validator; original documents never change.
Unknown capsule/slot fields fail: this is not an arbitrary packet patch API.
Fit/limits are supplied editorial judgments, not automated semantic approval.
Global used IDs must cover the book so far; additional identity reservations
cover historical identities outside this pool. No aliases/facts are inferred.

Callback integration: full composition/assessment/reviewer payloads contain
composition_binding={original_selection_sha256,case_capsule_sha256,...}. Pass
bind_composition_view(writing_view(payload), payload) to a JSON writing provider
when using an allowlisting/lean adapter. For the calibrated IndependentReviewer,
keep its raw system/prompt EXACTLY unchanged, use a reviewer cache under
new_work / composition_scope(payload), and bind the SAME composition_binding
to the raw provider dispatcher's source hashes/cache namespace. Do not JSON-wrap
the review prompt or share an unscoped review/provider cache: the existing
reviewer deliberately omits audit metadata from its calibrated evidence prompt.
This module supplies binding metadata; the caller owns those provider adapters.

Changed fit/case/proof/usage invalidates composition/review, not the discussion.
Use a fresh composition checkpoint namespace for a changed capsule; existing
council checkpoints correctly reject changed inputs. Hashes ensure integrity,
not external authenticity: callers select the trusted frozen snapshot directory.

Offline quality metadata: tests/test_source_first_case_capsule.py uses synthetic
facts and fake callbacks only. Structural PASS is not case-fit, factual, Sanskrit,
legal, publication or author approval. All five production models are untouched.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile

from scripts import prepare_source_first_book as preparation
from src.orchestration.source_first_stage import digest


SCHEMA = "source-first-case-capsule-v1"
POOL = "business-case-pool.json"
OVERLAY = "business-case-verification-overlay-complete.json"
_FIELDS = {"schema", "selection", "snapshots", "case_slots", "used_case_ids",
           "used_identity_keys", "capsule_sha256"}
_SLOT_FIELDS = {"kind", "case_id", "fit_reason_mr", "limitations_mr"}
_require = preparation.require


def _name(path):
    """Purpose: extract a portable filename from a recorded proof locator.

    Inputs: string path using either slash convention. Returns: local basename.
    Failures: ValueError for empty/dot/drive-qualified names; malformed input
    types fail rather than being coerced. Debug: inspect the original binding's
    path; do not repair a locator or substitute a different proof document.
    """
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    _require(name not in ("", ".", "..") and ":" not in name, "Invalid proof filename")
    return name


def _snapshot(path):
    """Purpose: freeze exact UTF-8 proof bytes without editing the source file.

    Inputs: local Path/string filename. Returns: name, byte SHA256, byte length
    and reversible raw_json text. Failures: I/O or Unicode errors propagate.
    Debug: compare the caller's frozen file bytes and encoding; reserializing a
    document would change its byte binding and is not a valid repair.
    """
    raw = Path(path).read_bytes()
    return {"name": Path(path).name, "sha256": preparation.byte_hash(raw),
            "bytes": len(raw), "raw_json": raw.decode("utf-8")}


def _decode(snapshot):
    """Purpose: validate a byte-bound snapshot before interpreting its JSON.

    Inputs: exact four-field snapshot dictionary. Returns: decoded JSON value.
    Failures: ValueError for schema/name/hash/length drift; invalid JSON or
    malformed types fail closed. Debug: check raw_json's UTF-8 bytes against the
    frozen artifact; never fix drift by silently recomputing the declared hash.
    """
    _require(isinstance(snapshot, dict) and set(snapshot) == {"name", "sha256", "bytes", "raw_json"},
             "Exact snapshot fields required")
    _require(isinstance(snapshot["name"], str) and _name(snapshot["name"]) == snapshot["name"],
             "Snapshot filename must be local")
    raw = snapshot["raw_json"].encode("utf-8")
    _require(snapshot["sha256"] == preparation.byte_hash(raw) and snapshot["bytes"] == len(raw),
             "Snapshot byte/hash drift")
    return json.loads(raw.decode("utf-8-sig"))


def _portable_overlay(overlay):
    """Normalize only merge-generated file locators for replay in a scratch root."""
    value = deepcopy(overlay)
    for field in ("input_bindings", "proof_artifacts"):
        for row in value[field]:
            row["path"] = _name(row["path"])
    for row in value["fact_verifications"]:
        if "merge_provenance" in row:
            row["merge_provenance"]["path"] = _name(row["merge_provenance"]["path"])
    return value


def _inventory(snapshots):
    """Purpose: replay complete fresh proof coverage and recover case constraints.

    Inputs: pool/overlay snapshots plus every exact input-proof snapshot.
    Returns: existing case_inventory tuple (cases, facts, identities, identity
    keys, conflicts). Failures: binding/coverage/replay ValueError, malformed
    schema errors or temporary-file I/O errors propagate before callbacks.
    Debug: compare the failing shard/original input binding and retained proof;
    missing proofs or HOLDs must not be relabelled as successful fresh checks.
    """
    _require(isinstance(snapshots, dict) and set(snapshots) == {"pool", "overlay", "proofs"},
             "Exact pool/overlay/proof snapshots required")
    pool, overlay = _decode(snapshots["pool"]), _decode(snapshots["overlay"])
    _require(snapshots["pool"]["name"] == POOL, "Canonical pool filename required")
    _require(overlay.get("status") == "COMPLETE_FACT_COVERAGE_WITH_EXPLICIT_HOLDS"
             and overlay.get("merge_kind") == "EXACT_ORIGINAL_AND_FOUR_FRESH_SHARDS",
             "Fresh complete overlay required")
    _require(isinstance(snapshots["proofs"], list), "Proof snapshots must be a list")
    documents = {POOL: snapshots["pool"]}
    for snapshot in snapshots["proofs"]:
        _decode(snapshot)
        _require(snapshot["name"] not in documents, "Duplicate proof snapshot")
        documents[snapshot["name"]] = snapshot
    bindings = overlay["input_bindings"]
    names = [_name(b["path"]) for b in bindings]
    _require(len(set(names)) == len(names) and set(names) == set(documents),
             "Complete exact proof coverage required")
    for binding, name in zip(bindings, names):
        snapshot = documents[name]
        _require(binding["sha256"] == snapshot["sha256"] and binding["bytes"] == snapshot["bytes"],
                 "Overlay input proof binding drift")
    # Replay includes exact shard ownership, every original audit, fact/record
    # bindings, coverage counts, limits and retained identity/relationship proofs.
    with tempfile.TemporaryDirectory(prefix="source-first-case-proof-") as directory:
        for name, snapshot in documents.items():
            (Path(directory) / name).write_bytes(snapshot["raw_json"].encode("utf-8"))
        replay = preparation.prepare_complete_case_overlay(directory)
    _require(_portable_overlay(overlay) == _portable_overlay(replay),
             "Complete overlay differs from exact fresh proof replay")
    return preparation.case_inventory(pool, overlay)


def _selection(number, brief, sources, discussion, proposal, peer_review):
    """Purpose: bind the exact accepted source-only entry and its arbitration.

    Inputs: positive entry number, original brief/packet, full batch discussion,
    and full-batch or selected proposal/three peer reviews. Returns: canonical
    selection hashes, including the council's unchanged original entry digest.
    Failures: ValueError for changed inputs, missing rounds/peers, malformed
    formula/pair references, REJECT or any unresolved peer REVIEW_REQUIRED.
    All three selected peers must be PASS with empty issues for this optional
    capsule flow. Debug: recover original saved records;
    changed source/selection inputs require a new appropriate discussion.
    """
    from src.orchestration.research_council import (
        SOURCE_FIRST_SELECTION, VOICES, _json, _numbered, _source_pair_ids, _check_answer,
    )
    _require(type(number) is int and number > 0, "Positive entry number required")
    _require(sources.get("examples") == [] and sources.get("case_assignments", []) == []
             and "case_capsule_provenance" not in sources,
             "Capsule requires the original source-only packet with examples=[]")
    batch = discussion.get("_batch", {})
    _require(batch.get("source_first_selection") == SOURCE_FIRST_SELECTION
             and number in batch.get("entry_numbers", []), "Accepted source-first batch required")
    original_hash = preparation.byte_hash(_json({"brief": brief, "sources": sources}).encode())
    _require(batch.get("entry_hashes", {}).get(str(number)) == original_hash,
             "Original brief/source hash drift")
    if "proposals" in proposal:
        proposal = _numbered(proposal["proposals"], batch["entry_numbers"], "Batch proposals")[number]
    _require(isinstance(peer_review, dict) and set(peer_review) == set(VOICES[:-1]),
             "Exactly three accepted-entry peer reviews required")
    peers = {}
    for role, review in peer_review.items():
        _require(isinstance(review, dict), "Peer review must be a dictionary")
        peers[role] = (_numbered(review["reviews"], batch["entry_numbers"], "Batch reviews")[number]
                       if "reviews" in review else review)
    _check_answer("proposal", "sutrakar", {"proposals": [proposal]},
                  {"scope": "batch", "entry_numbers": [number],
                   "source_first_selection": SOURCE_FIRST_SELECTION,
                   "sources_by_entry": {str(number): sources}})
    _require(proposal["decision"] == "ACCEPT", "Rejected entries cannot receive cases")
    if 'source_peer_policy' in batch:
        from src.orchestration.source_peer_evidence import require_entry_clear
        require_entry_clear(number, proposal, batch)
    for stage in ("position", "challenge", "reply"):
        records = discussion.get(stage)
        _require(isinstance(records, dict) and set(records) == set(VOICES),
                 "All four original discussion voices required")
        for role, record in records.items():
            _check_answer(stage, role, record, {"scope": "batch", "entry_numbers": batch["entry_numbers"]})
    for role, review in peers.items():
        _require(type(review.get("number")) is int and review["number"] == number,
                 "Peer review entry number drift")
        _check_answer("peer_review", role, review, {"proposal": proposal})
    _require(all(review["verdict"] == "PASS" and review["issues"] == [] for review in peers.values()),
             "Case capsule requires all three peer reviews PASS with empty issues; REVIEW_REQUIRED is held")
    pair, _ = _source_pair_ids(sources)
    result = {"number": number, "source_pair_ids": sorted(pair),
              "original_entry_sha256": original_hash, "brief_sha256": digest(brief),
              "sources_sha256": digest(sources), "proposal_sha256": digest(proposal),
              "discussion_sha256": digest(discussion), "peer_review_sha256": digest(peers)}
    result["selection_sha256"] = digest(result)
    return result


def _assignments(slots, inventory, used_ids, used_keys):
    """Purpose: attach two eligible cases without inventing identities or facts.

    Inputs: positive/caution slots with explicit fit/limits, validated inventory,
    sorted current used IDs and additional global identity reservation keys.
    Returns: copied DRAFT_ASSIGNED records with canonical case and full proofs.
    Failures: ValueError for slot/schema errors, unsupported facts, HOLDs,
    contradiction, identity reuse or cross-case conflicts. Debug: inspect the
    exact case/overlay/usage proof; semantic fit still needs independent review.
    """
    cases, facts, identities, keys, conflicts = inventory
    _require(isinstance(used_ids, list) and all(isinstance(i, str) for i in used_ids)
             and used_ids == sorted(set(used_ids)) and set(used_ids) <= set(cases),
             "Used case IDs must be unique, sorted and present in the frozen pool")
    _require(isinstance(used_keys, list) and all(isinstance(k, str) and k for k in used_keys)
             and used_keys == sorted(set(used_keys)), "Global identity reservations must be sorted unique keys")
    _require(all(k == preparation.normalized(k) or (k.startswith("case:") and k[5:])
                 for k in used_keys), "Global identity keys must use canonical reservation form")
    occupied = set(used_keys)
    for ident in used_ids:
        occupied.update(keys[ident])
    _require(isinstance(slots, list) and len(slots) == 2, "Exactly two case slots required")
    assigned, selected = [], list(used_ids)
    for slot, kind in zip(slots, ("positive", "caution")):
        _require(isinstance(slot, dict) and set(slot) == _SLOT_FIELDS,
                 "Only case ID, kind, fit and limitations may be supplied")
        _require(slot["kind"] == kind and all(preparation.text(slot[k]) for k in _SLOT_FIELDS),
                 "Positive then caution with explicit fit and limitations required")
        ident = slot["case_id"]
        _require(ident in cases, "Unknown canonical case")
        case, fact, identity = cases[ident], facts[ident], identities.get(ident)
        _require(case["kind"] == kind, "Canonical case kind mismatch")
        _require(not str(case.get("new_book_status", "")).startswith("HOLD")
                 and not any(str(flag).startswith("HOLD") for flag in case.get("flags", []))
                 and (identity is None or identity["status"] != "HOLD")
                 and fact["status"] in ("MATCH", "QUALIFIED")
                 and fact.get("existing_marathi_material_fact_contradiction_found") is not True,
                 f"{ident}: canonical/fact/identity HOLD or explicit contradiction")
        _require(ident not in selected and not (keys[ident] & occupied)
                 and not any((ident, prior) in conflicts for prior in selected),
                 f"{ident}: used identity or cross-case conflict")
        assigned.append({**deepcopy(slot), "status": "DRAFT_ASSIGNED",
                         "canonical_case": deepcopy(case), "verification": deepcopy(fact),
                         "identity_verification": deepcopy(identity),
                         "identity_reservations": sorted(keys[ident])})
        selected.append(ident)
        occupied.update(keys[ident])
    return assigned


def build_case_capsule(*, number, brief, sources, discussion, proposal, peer_review,
                       case_work_dir, case_slots, used_case_ids, used_identity_keys=(),
                       case_overlay_path=OVERLAY):
    """Read trusted snapshots and return a validated, JSON-serializable capsule.

    Full batch or selected proposal/peers are accepted. Inputs are never edited.
    Raises ValueError for stale selection, incomplete proofs, HOLDs, conflicts or
    unknown patch fields; file/JSON errors propagate. No provider is initialized.
    """
    work = Path(case_work_dir).resolve()
    overlay_path = Path(case_overlay_path)
    overlay_path = overlay_path if overlay_path.is_absolute() else work / overlay_path
    _require(overlay_path.resolve().parent == work, "Overlay must be in the snapshot directory")
    snapshots = {"pool": _snapshot(work / POOL), "overlay": _snapshot(overlay_path), "proofs": []}
    overlay = _decode(snapshots["overlay"])
    for binding in overlay["input_bindings"]:
        name = _name(binding["path"])
        if name != POOL:
            _require((work / name).resolve().parent == work, "Proof must stay inside snapshot directory")
            snapshots["proofs"].append(_snapshot(work / name))
    capsule = {"schema": SCHEMA,
               "selection": _selection(number, brief, sources, discussion, proposal, peer_review),
               "snapshots": snapshots, "case_slots": deepcopy(case_slots),
               "used_case_ids": sorted(used_case_ids), "used_identity_keys": sorted(used_identity_keys)}
    capsule["capsule_sha256"] = digest(capsule)
    apply_case_capsule(capsule, number=number, brief=brief, sources=sources,
                       discussion=discussion, proposal=proposal, peer_review=peer_review,
                       used_case_ids=used_case_ids)
    return capsule


def apply_case_capsule(capsule, *, number, brief, sources, discussion, proposal, peer_review, used_case_ids):
    """Validate exact bindings and return (effective_sources, composition_binding).

    Only examples, case_assignments and case_capsule_provenance may be added or
    replaced. Sources/brief/proposal/selection stay exact. Replay is offline and
    deterministic; this does not certify editorial fit or permit publication.
    """
    _require(isinstance(capsule, dict) and set(capsule) == _FIELDS and capsule["schema"] == SCHEMA,
             "Exact case capsule fields/schema required")
    _require(capsule["capsule_sha256"] == digest({k: v for k, v in capsule.items() if k != "capsule_sha256"}),
             "Case capsule hash drift")
    expected = _selection(number, brief, sources, discussion, proposal, peer_review)
    _require(capsule["selection"] == expected, "Accepted selection/proposal/discussion/peer binding drift")
    _require(capsule["used_case_ids"] == sorted(used_case_ids), "Current used case ledger drift")
    inventory = _inventory(capsule["snapshots"])
    assigned = _assignments(capsule["case_slots"], inventory,
                            capsule["used_case_ids"], capsule["used_identity_keys"])
    overlay = _decode(capsule["snapshots"]["overlay"])
    for item in assigned:
        item["relationship_provenance"] = [deepcopy(r) for r in overlay["cross_case_relationships"]
                                            if item["case_id"] in r["case_ids"]]
    binding = {"original_selection_sha256": expected["selection_sha256"],
               "case_capsule_sha256": capsule["capsule_sha256"],
               "original_entry_sha256": expected["original_entry_sha256"],
               "case_pool_sha256": capsule["snapshots"]["pool"]["sha256"],
               "case_overlay_sha256": capsule["snapshots"]["overlay"]["sha256"]}
    effective = deepcopy(sources)
    effective["examples"] = [{k: item["canonical_case"][k] for k in preparation.CASE_FIELDS} for item in assigned]
    effective["case_assignments"] = assigned
    effective["case_capsule_provenance"] = {"schema": SCHEMA, **binding,
                                             "capsule": deepcopy(capsule)}
    return effective, binding


def bind_composition_view(view, payload):
    """Retain exact binding after a caller's lean JSON projection; never wrap raw prompts.

    Legacy views are copied unchanged. Capsule payloads must carry matching source
    provenance; malformed/partial bindings fail. Provider callbacks remain caller-owned.
    """
    result = deepcopy(view)
    binding = payload.get("composition_binding")
    provenance = payload.get("sources", {}).get("case_capsule_provenance")
    if binding is None and provenance is None:
        return result
    _require(isinstance(binding, dict) and isinstance(provenance, dict)
             and set(binding) == {"original_selection_sha256", "case_capsule_sha256", "original_entry_sha256",
                                  "case_pool_sha256", "case_overlay_sha256"}
             and all(provenance.get(k) == v for k, v in binding.items()),
             "Composition/source capsule binding missing or inconsistent")
    result["composition_binding"] = deepcopy(binding)
    return result


def composition_scope(payload):
    """Return capsule-bound cache namespace for unchanged raw independent review.

    Use under the caller's NEW work root, for BOTH reviewer and provider caches.
    No directories/providers are created. Legacy payloads raise to avoid silently
    moving old cache namespaces; retain their original adapter path instead.
    """
    value = bind_composition_view({}, payload)
    _require("composition_binding" in value, "Capsule composition binding required")
    return "case-capsule-" + digest(value["composition_binding"])

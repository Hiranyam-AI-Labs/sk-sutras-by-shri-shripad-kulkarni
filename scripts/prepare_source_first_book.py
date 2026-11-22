"""Offline source-first book planning; no providers, keys, compositions or exports.

API:
  load_inputs(work, case_overlay=None) -> stage_plan/screening/pool/overlay + byte hashes.
  prepare_complete_case_overlay(work) -> complete fact overlay, preserving input proofs.
  --case-overlay PATH selects an optional overlay (relative to work or absolute).
  --merge-case-overlay creates business-case-verification-overlay-complete.json
  without overwriting originals; --output may name another new work-directory JSON.
  research_coverage(stage_plan, screening) -> coverage and eligible evidence cards.
  prepare_book_plan(stage_plan, screening, ordered_selection_cards, case_pool,
                    verification_overlay, pair_references, *, input_provenance=None)
      -> explicit DRAFT only after complete research coverage.

Each selection card declares card_id, cluster_id, representative_pair_id,
alternative_pairs=[{pair_id, same_decision_action_reason_mr}], topic_mr,
decision_mr, action_mr, source_derivation_mr, cluster_rationale_mr,
journey_stage, ordering_reason_mr, selection_provenance={curator, rationale_mr},
case_slots=[{kind:"positive", case_id:ID|null, fit_reason_mr, limitations_mr},
            {kind:"caution", case_id:ID|null, fit_reason_mr, limitations_mr}].
For a null case_id use unassigned_reason_mr instead of fit/limitations.
No quote, case fact, new formula or thematic score may be supplied in a card.

Callers curate semantics, alternatives and journey order. This code only rejects
declared cluster duplication and identical decision/action text, never claims to
detect semantic equivalence. Distinct paraphrases still require editorial review.
pair_references is a trusted caller-curated mapping of N<number>/S<number> to
the existing eight-field reference schema. Exact Sanskrit and meaning must
match the frozen source records; complete contexts are retained alongside them.
Cases without a MATCH/QUALIFIED fact overlay remain UNASSIGNED. Identity-only
checks never qualify facts. Qualified use retains the entire overlay and limits.
Old positive/caution framing is not evidence of truth or new-book fit.

CLI reads only and writes JSON to stdout by default. Optional --output may create
a NEW .json file within the work directory; it never overwrites an existing file.
Missing research batches return a non-DRAFT coverage diagnostic and exit code 2.
Completed dispositions include PENDING: these pairs remain excluded but do not
block eligible SUPPORTED/independent-PASS pairs. No source meaning is generated.
"""
from collections import Counter
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.orchestration.research_acceptance import REFERENCE_FIELDS, CASE_FIELDS
from src.orchestration.source_first_research import (
    prepare_research_batch, validate_research_selection, ASSESSMENT_FIELDS,
)
from src.orchestration.source_first_stage import digest, validate_evidence_review

WORK = ROOT / "logs/source-first-generation-20261120"
JOURNEY = {"opening": 0, "practice": 1, "growth": 2, "people": 2, "society": 2, "closure": 3}
CARD_FIELDS = {
    "card_id", "cluster_id", "representative_pair_id", "alternative_pairs",
    "topic_mr", "decision_mr", "action_mr", "source_derivation_mr",
    "cluster_rationale_mr", "journey_stage", "ordering_reason_mr",
    "selection_provenance", "case_slots",
}


def require(value, message):
    if not value:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def byte_hash(raw):
    return hashlib.sha256(raw).hexdigest()


def normalized(label):
    """Literal identity reservation only; not fuzzy identity or semantic matching."""
    return "".join(c for c in unicodedata.normalize("NFKC", label).casefold() if c.isalnum())


def indexed(rows, field, label):
    require(isinstance(rows, list) and all(isinstance(r, dict) and text(r.get(field))
                                          for r in rows), f"{label}: malformed records")
    result = {r[field]: r for r in rows}
    require(len(rows) == len(result), f"{label}: duplicate {field}")
    return result


def research_coverage(plan, screening):
    """Replay exact canonical requests/selections and independent verdict gates.

    Missing batches block plan creation. Completed PENDING, UNSUPPORTED and
    REVIEW_REQUIRED dispositions are accounted for but never eligible; PENDING
    does not block other eligible pairs once every planned batch is present.
    A gate is a trusted recorded independent verdict, not a cryptographic signature
    or a fresh independent semantic review by this preparation code.
    """
    require(plan.get("plan_sha256") == digest({k: v for k, v in plan.items() if k != "plan_sha256"}),
            "research-stage-plan hash drift")
    candidates = indexed(plan["candidates"], "id", "stage candidates")
    library = indexed(plan["library"], "source_id", "stage library")
    source_pairs = set()
    for ident, candidate in candidates.items():
        n, sh = candidate["narada"]["id"], candidate["shandilya"]["id"]
        require(type(n) is int and 1 <= n <= 84 and type(sh) is int and 1 <= sh <= 100,
                "strict scalar Narada/Shandilya IDs required")
        require(ident == f"N{n:03d}-S{sh:03d}" and (n, sh) not in source_pairs,
                "canonical candidate ID or duplicate scalar pair")
        source_pairs.add((n, sh))
    require(plan["candidate_count"] == len(candidates)
            and plan["reference_count"] == len(library), "stage count mismatch")
    batches = plan["batches"]
    require(isinstance(batches, list) and batches and all(isinstance(b, list) and b for b in batches),
            "stage batch partition required")
    flat = [i for batch in batches for i in batch]
    require(all(text(i) for i in flat) and len(flat) == len(set(flat))
            and set(flat) == set(candidates), "stage batches must partition candidates exactly")
    expected_names = [f"research-{i:03d}" for i in range(1, len(batches) + 1)]
    require(isinstance(screening, dict) and set(screening) <= set(expected_names),
            "unknown screening batch")
    missing, pending, eligible, dispositions, provenance = [], [], {}, {}, {}
    for name, identifiers in zip(expected_names, batches):
        if name not in screening:
            missing.append(name)
            continue
        bundle = screening[name]
        require(set(bundle) >= {"request", "selection", "gate"}, f"{name}: incomplete bundle")
        supplied = [candidates[i] for i in identifiers]
        evidence = [{**deepcopy(ref), "id": f"{c['id']}::{ref['source_id']}", "candidate_id": c["id"]}
                    for c in supplied for ref in plan["library"]]
        request = prepare_research_batch(name, supplied, evidence, plan["source_hashes"])
        require(bundle["request"] == request, f"{name}: request differs from frozen plan")
        selection, gate = bundle["selection"], bundle["gate"]
        require(selection.get("status") == "PASS", f"{name}: selection gate failed")
        raw_rows = [{k: r[k] for k in ASSESSMENT_FIELDS} for r in selection["assessments"]]
        envelope = {k: request[k] for k in ("batch_id", "request_sha256", "source_hashes")}
        expected_selection = validate_research_selection(request, {**envelope, "assessments": raw_rows})
        require(selection == expected_selection, f"{name}: canonical selection/evidence drift")
        require(gate.get("status") == "EVIDENCE_SCREENED"
                and gate.get("request_sha256") == request["request_sha256"]
                and gate.get("selection_sha256") == digest(selection), f"{name}: exact gate hash drift")
        reviews = validate_evidence_review(identifiers, {"decisions": gate["review"]})
        review_by_id = {r["candidate_id"]: r for r in reviews}
        supported = [r["candidate_id"] for r in selection["assessments"]
                     if r["status"] == "SUPPORTED" and review_by_id[r["candidate_id"]]["verdict"] == "PASS"]
        held = [i for i in identifiers if review_by_id[i]["verdict"] != "PASS"]
        require(gate.get("supported_and_reviewed") == supported
                and gate.get("held_for_review") == held, f"{name}: eligibility ledger drift")
        provenance[name] = {"request_sha256": request["request_sha256"],
                            "selection_sha256": digest(selection), "gate_sha256": digest(gate),
                            "files": deepcopy(bundle.get("files", {}))}
        for assessment in selection["assessments"]:
            ident = assessment["candidate_id"]
            dispositions[ident] = {"research_status": assessment["status"],
                                  "independent_review": deepcopy(review_by_id[ident])}
            if assessment["status"] == "PENDING":
                pending.append(ident)
            if ident in supported:
                eligible[ident] = {"candidate": deepcopy(candidates[ident]),
                                   "research": deepcopy(assessment),
                                   "independent_review": deepcopy(review_by_id[ident]),
                                   "batch_id": name, "batch_provenance": deepcopy(provenance[name])}
    return {"status": "COMPLETE" if not missing else "INCOMPLETE",
            "expected_pairs": len(candidates), "screened_pairs": len(dispositions),
            "expected_batches": len(batches), "completed_batches": len(screening),
            "missing_batches": missing, "pending_pair_ids": pending,
            "eligible": eligible, "dispositions": dispositions, "batches": provenance}


def case_inventory(pool, overlay):
    """Retain exact cases/overlays and conservative shared-label reservations."""
    cases = indexed(pool["cases"], "case_id", "case pool")
    require(pool["case_count"] == len(cases), "case pool count mismatch")
    facts, identities = {}, {}
    keys = {}
    for ident, case in cases.items():
        require(all(text(case.get(k)) for k in (*CASE_FIELDS, "recorded_fact")),
                f"{ident}: missing canonical case fields/fact")
        identity = case["entity_identity"]
        labels = [case["entity"], identity["normalized_entity_key"],
                  *identity["deduplication_keys"], *identity["recorded_aliases_and_related_labels"]]
        require(all(text(label) for label in labels), f"{ident}: malformed identity labels")
        keys[ident] = {normalized(label) for label in labels}
        keys[ident].add("case:" + case.get("canonical_case_id", ident))
    for field, dest in (("fact_verifications", facts), ("identity_verifications", identities)):
        for check in overlay[field]:
            ident = check["case_id"]
            require(ident in cases and ident not in dest
                    and check["case_pool_record_sha256"] == digest(cases[ident]),
                    f"{ident}: overlay case hash drift/duplicate")
            require(check["status"] in ("MATCH", "QUALIFIED", "HOLD"), f"{ident}: overlay status")
            if "existing_marathi_material_fact_contradiction_found" in check:
                require(type(check["existing_marathi_material_fact_contradiction_found"]) is bool,
                        f"{ident}: contradiction flag must be boolean when supplied")
            dest[ident] = deepcopy(check)
            if field == "fact_verifications":
                require(check["existing_text_mr_sha256"] == byte_hash(cases[ident]["text_mr"].encode())
                        and check["existing_recorded_fact_sha256"] == byte_hash(cases[ident]["recorded_fact"].encode()),
                        f"{ident}: overlay fact/text hash drift")
            elif check["status"] != "HOLD":
                keys[ident].update(normalized(r["label"]) for r in check["verified_relationships"])
    conflicts = set()
    for relation in overlay["cross_case_relationships"]:
        ids = relation["case_ids"]
        require(all(i in cases and relation["case_record_bindings"].get(i) == digest(cases[i])
                    for i in ids), "cross-case relationship binding drift")
        # Reserve all recorded shared persons, without claiming common ownership,
        # legal equivalence, or responsibility for someone else's case incident.
        if text(relation.get("person")):
            for ident in ids:
                keys[ident].add(normalized(relation["person"]))
        for i in ids:
            for j in ids:
                if i != j:
                    conflicts.add((i, j))
    return cases, facts, identities, keys, conflicts


def pair_packet(evidence, references):
    """Copy exact canonical 8-field references; no quote regeneration."""
    candidate = evidence["candidate"]
    pair_ids, refs, contexts = [], [], {}
    for name, prefix in (("narada", "N"), ("shandilya", "S")):
        source = candidate[name]
        require(type(source["id"]) is int and source["id"] > 0, "scalar source ID required")
        ident = prefix + str(source["id"])
        require(ident in references, f"mandatory canonical reference missing: {ident}")
        ref = references[ident]
        require(isinstance(ref, dict) and set(ref) == set(REFERENCE_FIELDS)
                and all(text(ref[k]) for k in REFERENCE_FIELDS), f"{ident}: exact eight reference fields required")
        require(ref["id"] == ident and ref["original_text"] == source["sanskrit"]
                and ref["meaning_mr"] == source["meaning_mr"], f"{ident}: canonical pair quote/meaning drift")
        require(re.match(r"^https?://[^/\s]+", ref["url"]) is not None, f"{ident}: source URL required")
        pair_ids.append(ident)
        refs.append(deepcopy(ref))
        contexts[ident] = deepcopy(source)
    for selected in evidence["research"]["selected_evidence"]:
        source = selected["source_record"]
        ref = {"id": selected["source_id"], "title": selected["title"], "author": source["author"],
               "locator": selected["location"], "original_text": selected["canonical_passage"],
               "meaning_mr": selected["meaning_mr"],
               "url": source.get("primary_url", source.get("url")), "tradition": "Indian"}
        require(all(text(ref.get(k)) for k in REFERENCE_FIELDS)
                and re.match(r"^https?://[^/\s]+", ref["url"]) is not None,
                "selected supplementary reference missing canonical eight fields")
        require(ref["id"] not in pair_ids and selected["verified"] and selected["eligible"],
                "supplementary evidence is a pair repeat or ineligible")
        require(selected["passage_sha256"] == byte_hash(ref["original_text"].encode()),
                "supplementary quote hash drift")
        refs.append(ref)
        contexts[ref["id"]] = deepcopy(selected)
    require(len(refs) > 2 and len({r["id"] for r in refs}) == len(refs), "distinct supplementary support required")
    return {"source_pair_ids": pair_ids, "pair_reference_ids": list(pair_ids),
            "references": refs, "source_contexts": contexts,
            "source_hashes": deepcopy(candidate["source_hashes"]), "examples": []}


def prepare_book_plan(stage_plan, screening, ordered_selection_cards, case_pool,
                      verification_overlay, pair_references, *, input_provenance=None):
    """Create a DRAFT candidate plan from explicit editorial judgments only.

    Non-ready cases become UNASSIGNED with reasons. Unknown case IDs, blank fit
    reasons, repeated identities, semantic-card omissions and stale evidence raise.
    No author approval, final case allocation or council readiness is inferred.
    """
    coverage = research_coverage(stage_plan, screening)
    require(coverage["status"] == "COMPLETE",
            f"research coverage incomplete: missing batches {coverage['missing_batches']}")
    require(isinstance(ordered_selection_cards, list), "explicit ordered selection cards required")
    require(isinstance(pair_references, dict), "canonical pair reference registry required")
    cases, facts, identities, identity_keys, conflicts = case_inventory(case_pool, verification_overlay)
    entries, seen_cards, seen_clusters, used_pairs, used_cases, used_keys, decisions = [], set(), set(), set(), set(), set(), set()
    previous_stage = -1
    for number, card in enumerate(ordered_selection_cards, 1):
        require(isinstance(card, dict) and set(card) == CARD_FIELDS, "exact explicit selection-card schema required")
        for k in CARD_FIELDS - {"alternative_pairs", "case_slots", "selection_provenance"}:
            require(text(card[k]), f"selection card requires {k}")
        require(card["card_id"] not in seen_cards and card["cluster_id"] not in seen_clusters,
                "duplicate card/decision cluster: merge alternatives before council work")
        decision = tuple(" ".join(card[k].casefold().split()) for k in ("decision_mr", "action_mr"))
        require(decision not in decisions, "identical decision/action: curator must merge duplicate clusters")
        require(card["journey_stage"] in JOURNEY, "unknown reader journey stage")
        rank = JOURNEY[card["journey_stage"]]
        require(rank >= previous_stage, "ordered cards reverse the reader journey")
        previous_stage = rank
        curator = card["selection_provenance"]
        require(isinstance(curator, dict) and set(curator) == {"curator", "rationale_mr"}
                and all(text(curator.get(k)) for k in ("curator", "rationale_mr")),
                "explicit semantic curator provenance required")
        require(isinstance(card["alternative_pairs"], list), "explicit alternatives list required")
        pair_ids = [card["representative_pair_id"]]
        for alternative in card["alternative_pairs"]:
            require(isinstance(alternative, dict) and set(alternative) == {"pair_id", "same_decision_action_reason_mr"}
                    and all(text(v) for v in alternative.values()), "alternative requires explicit same-decision rationale")
            pair_ids.append(alternative["pair_id"])
        require(len(pair_ids) == len(set(pair_ids)) and not used_pairs.intersection(pair_ids),
                "pair reused within/across editorial clusters")
        require(all(i in coverage["eligible"] for i in pair_ids), "only SUPPORTED and independent PASS pairs eligible")
        evidence = coverage["eligible"][pair_ids[0]]
        packet = pair_packet(evidence, pair_references)
        slots = card["case_slots"]
        require(isinstance(slots, list) and len(slots) == 2
                and all(isinstance(slot, dict) for slot in slots)
                and [s.get("kind") for s in slots] == ["positive", "caution"],
                "exactly two ordered positive/caution case slots required")
        assignments = []
        for slot in slots:
            ident = slot.get("case_id")
            if ident is None:
                require(set(slot) == {"kind", "case_id", "unassigned_reason_mr"}
                        and text(slot["unassigned_reason_mr"]), "UNASSIGNED slot requires reason")
                assignments.append({**deepcopy(slot), "status": "UNASSIGNED"})
                continue
            require(text(ident) and ident in cases, "unknown exact case ID")
            require(set(slot) == {"kind", "case_id", "fit_reason_mr", "limitations_mr"}
                    and text(slot["fit_reason_mr"]) and text(slot["limitations_mr"]),
                    "case assignment requires explicit fit reason and limits; no rewritten facts")
            case, fact = cases[ident], facts.get(ident)
            require(case["kind"] == slot["kind"], "case kind/order mismatch")
            identity = identities.get(ident)
            held = (case.get("new_book_status", "").startswith("HOLD")
                    or any(str(flag).startswith("HOLD") for flag in case.get("flags", []))
                    or (identity and identity["status"] == "HOLD")
                    or not fact or fact["status"] == "HOLD"
                    # Fresh shard MATCH/QUALIFIED verdicts need not contain the legacy
                    # contradiction boolean. Never manufacture an absent "False";
                    # an explicit contradiction still overrides the verdict.
                    or fact.get("existing_marathi_material_fact_contradiction_found") is True)
            if held:
                assignments.append({**deepcopy(slot), "requested_case_id": ident, "case_id": None,
                                    "status": "UNASSIGNED", "unassigned_reason_mr":
                                    "Case lacks a usable exact fact verification or has a HOLD; curator must choose another.",
                                    "verification": deepcopy(fact), "identity_verification": deepcopy(identity)})
                continue
            require(ident not in used_cases and not identity_keys[ident].intersection(used_keys)
                    and not any((ident, other) in conflicts for other in used_cases),
                    f"repeated case/person/business/related-entity reservation: {ident}")
            used_cases.add(ident)
            used_keys.update(identity_keys[ident])
            assignments.append({**deepcopy(slot), "status": "DRAFT_ASSIGNED",
                                "canonical_case": deepcopy(case), "verification": deepcopy(fact),
                                "identity_verification": deepcopy(identity),
                                "identity_reservations": sorted(identity_keys[ident]),
                                "relationship_provenance": [deepcopy(r) for r in verification_overlay["cross_case_relationships"]
                                                            if ident in r["case_ids"]]})
            packet["examples"].append({k: deepcopy(case[k]) for k in CASE_FIELDS})
        alternatives = [{"pair_id": ident, "reason_mr": alt["same_decision_action_reason_mr"],
                         "research_provenance": deepcopy(coverage["eligible"][ident])}
                        for ident, alt in zip(pair_ids[1:], card["alternative_pairs"])]
        provenance = {"selection_card_sha256": digest(card), "selection_card": deepcopy(card),
                      "representative": deepcopy(evidence), "alternative_pairs": alternatives}
        packet["selection_provenance"] = deepcopy(provenance)
        packet["case_assignments"] = deepcopy(assignments)
        ready = all(s["status"] == "DRAFT_ASSIGNED" for s in assignments)
        brief = {"number": number, "topic_mr": card["topic_mr"], "decision_mr": card["decision_mr"],
                 "action_mr": card["action_mr"], "source_derivation_mr": card["source_derivation_mr"],
                 "journey_stage": card["journey_stage"], "ordering_reason_mr": card["ordering_reason_mr"],
                 "pair_reference_ids": list(packet["pair_reference_ids"]),
                 "selection_provenance": deepcopy(provenance)}
        entries.append({"number": number, "status": "DRAFT", "pair_id": pair_ids[0],
                        "cluster_id": card["cluster_id"], "brief": brief, "source_packet": packet,
                        "case_assignments": assignments, "council_ready": ready})
        seen_cards.add(card["card_id"]); seen_clusters.add(card["cluster_id"])
        decisions.add(decision); used_pairs.update(pair_ids)
    return {"schema_version": 1, "status": "DRAFT", "new_sutras": 0, "paid_calls": 0,
            "author_approval": "PENDING", "publication_approved": False,
            "semantic_judgments": "Caller-curated cards; structural preparation is not semantic validation.",
            "source_stage_plan_sha256": stage_plan["plan_sha256"],
            "research_coverage": {k: deepcopy(v) for k, v in coverage.items() if k != "eligible"},
            "input_provenance": deepcopy(input_provenance or {}),
            "selection_cards_sha256": digest(ordered_selection_cards),
            "canonical_pair_references_sha256": digest(pair_references),
            "case_pool_sha256": digest(case_pool), "case_verification_overlay_sha256": digest(verification_overlay),
            "reader_journey": list(JOURNEY), "protected_opening_closing_assets": "EXTERNAL_UNCHANGED_NOT_REGENERATED",
            "entries": entries,
            "unselected_eligible_pair_ids": [i for i in coverage["eligible"] if i not in used_pairs],
            "council_payload": {"briefs": [deepcopy(e["brief"]) for e in entries if e["council_ready"]],
                               "sources_by_entry": {str(e["number"]): deepcopy(e["source_packet"])
                                                    for e in entries if e["council_ready"]}},
            "requires_final_curation_and_independent_validation": True}



def prepare_complete_case_overlay(work=WORK):
    """Merge recorded verification decisions only; perform no new fact review.

    Original fact records and identity proofs stay unchanged. Fresh records keep
    all fields verbatim, with missing canonical/text/fact binding hashes computed
    from the current pool and explicitly labelled as structural additions.
    Each entire original proof document is embedded alongside its exact byte hash.
    Missing, overlapping, foreign or wrong-shard IDs and any binding drift fail.
    """
    work = Path(work).resolve()
    documents, snapshots = {}, {}
    def read(name):
        require(Path(name).name == name, "proof filename must be local to work")
        raw = (work / name).read_bytes()
        snapshots[name] = raw
        documents[name] = json.loads(raw.decode("utf-8-sig"))
        return documents[name]
    def artifact_path(name):
        path = work / name
        return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
    pool_name = "business-case-pool.json"
    original_name = "business-case-verification-overlay.json"
    pool, original = read(pool_name), read(original_name)
    cases = indexed(pool["cases"], "case_id", "case pool")
    require(pool["case_count"] == len(cases), "case pool count mismatch")
    pool_hash, original_hash = byte_hash(snapshots[pool_name]), byte_hash(snapshots[original_name])
    def bound_hash(bindings, filename):
        return next((b["sha256"] for b in bindings
                     if b["path"].replace("\\", "/").rsplit("/", 1)[-1] == filename), None)
    require(bound_hash(original["input_bindings"], pool_name) == pool_hash,
            "original overlay whole-pool byte binding drift")
    # Preserve and recheck every original input binding, including its audit.
    for binding in original["input_bindings"]:
        name = binding["path"].replace("\\", "/").rsplit("/", 1)[-1]
        if name not in snapshots:
            read(name)
        require(byte_hash(snapshots[name]) == binding["sha256"], f"original input proof drift: {name}")
        if "bytes" in binding:
            require(len(snapshots[name]) == binding["bytes"], f"original input byte length drift: {name}")
    original_facts = indexed(original["fact_verifications"], "case_id", "original facts")
    require(all(r["status"] in ("MATCH", "QUALIFIED") for r in original_facts.values()),
            "original HOLD facts require explicit resolution before this exclusion-based merge")
    merged = deepcopy(original_facts)
    proof_names = [original_name]
    for shard_index in range(4):
        name = f"business-case-fresh-shard-{shard_index}.json"
        shard = read(name)
        proof_names.append(name)
        require(str(shard.get("status", "")).startswith("COMPLETE"), f"incomplete shard {shard_index}")
        require(shard.get("shard_index", shard.get("shard", shard_index)) == shard_index,
                f"wrong shard declaration {shard_index}")
        bindings = shard.get("input_bindings")
        if isinstance(bindings, list):
            shard_pool = bound_hash(bindings, pool_name)
            shard_original = bound_hash(bindings, original_name)
        elif isinstance(bindings, dict):
            shard_pool, shard_original = bindings.get("pool_sha256"), bindings.get("overlay_sha256")
        else:
            shard_pool = shard.get("pool_sha256")
            shard_original = shard.get("overlay_sha256_at_selection", shard.get("excluded_overlay_sha256"))
        require(shard_pool == pool_hash and shard_original == original_hash,
                f"shard {shard_index}: pool/original byte hash drift")
        rows = indexed(shard["records"], "case_id", f"shard {shard_index}")
        expected = {c["case_id"] for i, c in enumerate(pool["cases"])
                    if i % 4 == shard_index and c["case_id"] not in original_facts}
        require(set(rows) == expected, f"shard {shard_index}: exact assigned coverage required")
        for position, raw in enumerate(shard["records"]):
            ident = raw["case_id"]
            require(ident not in merged, f"duplicate fact verification: {ident}")
            case = cases[ident]
            canonical = digest(case)
            declared = [raw[k] for k in ("canonicalcasehash", "case_pool_record_sha256") if k in raw]
            require(declared and all(h == canonical for h in declared),
                    f"{ident}: canonical case hash drift")
            require(raw.get("status") in ("MATCH", "QUALIFIED", "HOLD")
                    and all(text(raw.get(k)) for k in ("checked_date_local", "exact_supported_fact",
                                                     "reason_mr", "limitations_mr")),
                    f"{ident}: incomplete fresh proof")
            require(isinstance(raw.get("primary_urls"), list) and raw["primary_urls"]
                    and all(text(url) and re.match(r"^https?://[^/\s]+", url)
                            for url in raw["primary_urls"]), f"{ident}: primary URLs required")
            check = deepcopy(raw)
            added = []
            for key, expected_hash in (
                ("case_pool_record_sha256", canonical),
                ("existing_text_mr_sha256", byte_hash(case["text_mr"].encode())),
                ("existing_recorded_fact_sha256", byte_hash(case["recorded_fact"].encode())),
            ):
                if key in check:
                    require(check[key] == expected_hash, f"{ident}: fresh structural binding drift")
                else:
                    check[key] = expected_hash
                    added.append(key)
            check["merge_provenance"] = {
                "path": artifact_path(name), "sha256": byte_hash(snapshots[name]),
                "json_pointer": f"/records/{position}", "original_record_sha256": digest(raw),
                "structurally_added_binding_fields": added,
                "scope": "Computed hashes bind existing pool bytes; no new factual verification claim.",
            }
            merged[ident] = check
    require(set(merged) == set(cases), "merged fact coverage must equal the entire pool")
    result = deepcopy(original)
    counts = dict(Counter(merged[i]["status"] for i in cases))
    result.update({
        "status": "COMPLETE_FACT_COVERAGE_WITH_EXPLICIT_HOLDS",
        "merge_kind": "EXACT_ORIGINAL_AND_FOUR_FRESH_SHARDS",
        "reviewer": "Recorded original/shard verifiers; this artifact performs structural merging only",
        "method": [
            "Replay pool, original-overlay and shard byte/record bindings.",
            "Retain original fact decisions, complete proof documents and identity/relationship records.",
            "Normalize only missing structural hash fields; no fresh review or inferred negative findings.",
        ],
        "operations": {"paid_api_calls": 0, "new_sutras": 0, "new_fact_reviews": 0,
                       "source_or_book_edits": 0, "case_assignments": 0},
        "verification_date": "2026-11-21",
        "scope": "Structural merge of original fresh fact decisions and four fresh shards; no new source/API calls or semantic reassessment.",
        "fact_verifications": [merged[i] for i in cases],
        "original_overlay_metadata": {k: deepcopy(v) for k, v in original.items()
                                      if k not in ("fact_verifications", "identity_verifications",
                                                   "cross_case_relationships")},
        "proof_artifacts": [{"path": artifact_path(name), "sha256": byte_hash(snapshots[name]),
                             "bytes": len(snapshots[name]), "document": deepcopy(documents[name])}
                            for name in proof_names],
        "input_bindings": [{"path": artifact_path(name), "sha256": byte_hash(raw), "bytes": len(raw)}
                           for name, raw in snapshots.items()],
        "coverage": {
            "pool_records": len(cases), "fact_records": len(merged),
            "original_fact_records": len(original_facts),
            "fresh_shard_fact_records": len(merged) - len(original_facts),
            "fact_dispositions": counts,
            "identity_records": len(original["identity_verifications"]),
            "identity_dispositions": dict(Counter(r["status"] for r in original["identity_verifications"])),
            "identity_hold_case_ids": [r["case_id"] for r in original["identity_verifications"] if r["status"] == "HOLD"],
            "fact_hold_case_ids": [i for i in cases if merged[i]["status"] == "HOLD"],
            "cross_case_relationship_findings": len(original["cross_case_relationships"]),
        },
        "merge_operations": {"paid_api_calls": 0, "new_sutras": 0, "new_fact_reviews": 0,
                             "source_artifacts_modified": False, "original_proofs_preserved": True},
    })
    case_inventory(pool, result)
    for name, raw in snapshots.items():
        require((work / name).read_bytes() == raw, f"proof changed during merge: {name}")
    return result


def load_inputs(work=WORK, case_overlay=None):
    """Read a consistent snapshot with an optional, exact pool-bound overlay.

    Relative overlay paths resolve inside work. A complete merged overlay is
    reconstructed from its original proof artifacts, failing on any drift.
    """
    work = Path(work).resolve()
    snapshots = {}
    def load(relative):
        path = work / relative
        raw = path.read_bytes()
        snapshots[relative] = raw
        return json.loads(raw.decode("utf-8-sig"))
    plan = load("research-stage-plan.json")
    pool = load("business-case-pool.json")
    overlay_path = Path(case_overlay) if case_overlay is not None else Path("business-case-verification-overlay.json")
    overlay = load(str(overlay_path))
    if overlay.get("merge_kind") == "EXACT_ORIGINAL_AND_FOUR_FRESH_SHARDS":
        require(overlay == prepare_complete_case_overlay(work), "merged overlay/proof artifact drift")
    pool_binding = next((b for b in overlay["input_bindings"] if Path(b["path"]).name == "business-case-pool.json"), None)
    require(pool_binding is not None and pool_binding["sha256"] == byte_hash(snapshots["business-case-pool.json"]),
            "overlay whole-pool byte binding drift")
    source_paths = {
        "narada": "../20261119-sutra-comparison/narada-working.json",
        "shandilya": "../20261119-sutra-comparison/shandilya-working.json",
        "candidate_manifest": "candidate-manifest.json",
        "evidence_corpus": "evidence-corpus.json",
        "corpus_review": "evidence-corpus-independent-review.json",
        "primary_verification": "evidence-primary-verification.json",
        "devotional_supplement": "evidence-devotional-supplement.json",
        "devotional_review": "evidence-devotional-independent-review.json",
    }
    for key, relative in source_paths.items():
        if key in plan["source_hashes"]:
            load(relative)
            require(byte_hash(snapshots[relative]) == plan["source_hashes"][key],
                    f"current source file hash drift: {key}")
    screening = {}
    for n in range(1, len(plan["batches"]) + 1):
        name = f"research-{n:03d}"
        paths = {k: f"research-screening/{name}-{k}.json" for k in ("request", "selection", "gate")}
        if not all((work / p).is_file() for p in paths.values()):
            continue
        bundle = {k: load(p) for k, p in paths.items()}
        bundle["files"] = {k: {"path": p, "sha256": byte_hash(snapshots[p])} for k, p in paths.items()}
        screening[name] = bundle
    for path, raw in snapshots.items():
        require((work / path).read_bytes() == raw, f"input changed while reading: {path}")
    return {"stage_plan": plan, "screening": screening, "case_pool": pool,
            "verification_overlay": overlay,
            "input_provenance": {p: {"sha256": byte_hash(b), "bytes": len(b)} for p, b in snapshots.items()}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=WORK)
    parser.add_argument("--case-overlay", type=Path, help="Optional overlay; relative to work or absolute")
    parser.add_argument("--merge-case-overlay", action="store_true",
                        help="Create a new complete fact overlay from the four frozen shards")
    parser.add_argument("--cards", type=Path)
    parser.add_argument("--pair-references", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.merge_case_overlay:
        merged = prepare_complete_case_overlay(args.work)
        output = (args.output or args.work / "business-case-verification-overlay-complete.json").resolve()
        require(output.is_relative_to(args.work.resolve()) and output.suffix == ".json",
                "merged overlay output must be a new work-directory JSON")
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(merged, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"path": str(output), "coverage": merged["coverage"]}, ensure_ascii=False))
        return 0
    inputs = load_inputs(args.work, case_overlay=args.case_overlay)
    coverage = research_coverage(inputs["stage_plan"], inputs["screening"])
    if coverage["status"] != "COMPLETE":
        print(json.dumps({k: v for k, v in coverage.items() if k != "eligible"}, ensure_ascii=False, indent=2))
        return 2
    require(args.cards is not None and args.pair_references is not None, "complete coverage still requires explicit cards and canonical pair references")
    inputs["ordered_selection_cards"] = json.loads(args.cards.read_text(encoding="utf-8-sig"))
    inputs["pair_references"] = json.loads(args.pair_references.read_text(encoding="utf-8-sig"))
    result = prepare_book_plan(**inputs)
    raw = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output is None:
        print(raw, end="")
    else:
        output = args.output.resolve()
        require(output.is_relative_to(args.work.resolve()) and output.suffix == ".json",
                "output must be a new JSON file inside the work directory")
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

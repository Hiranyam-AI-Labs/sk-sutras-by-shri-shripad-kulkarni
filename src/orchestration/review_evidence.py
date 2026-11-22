"""Typed references to immutable review evidence; no provider or verdict decisions."""

import hashlib
import json
import re
import unicodedata
from copy import deepcopy


def decision_comparisons(payload):
    """Pair the current business decision/action with every prior chapter.

    Return factual comparison context, never semantic model labels. Missing
    current/prior decision evidence or duplicate identities raise before spending.
    Equality ignores only Unicode normalization and whitespace, not meaning.
    Inspect paired fields to distinguish shared themes from repeated actions.
    """
    draft, cards = payload["current_draft"], payload["comparison_chapters"]
    current = {"decision_mr": draft.get("summary_mr", ""), "action_mr": draft.get("action_mr", "")}
    if cards and any(not isinstance(value, str) or not value.strip() for value in current.values()):
        raise ValueError("Decision comparison requires current summary_mr and action_mr")
    def normalized(text):
        """Normalize equivalent Unicode/spacing only; return text for exact checks."""
        return " ".join(unicodedata.normalize("NFC", text).split())
    seen, prior = set(), []
    for card in cards:
        if any(not isinstance(card.get(k), str) or not card[k].strip()
               for k in ("id", "formula", "decision_mr", "action_mr")) or card["id"] in seen:
            raise ValueError("Prior decisions require unique identities and complete evidence")
        seen.add(card["id"])
        prior.append({**deepcopy(card),
            "same_formula": re.sub(r"[\s।॥]+", "", card["formula"]) == re.sub(r"[\s।॥]+", "", draft["new_sutra"]),
            "identical_decision_and_action": all(normalized(current[k]) == normalized(card[k])
                                                  for k in ("decision_mr", "action_mr"))})
    return {"current": current, "prior": prior}


def validate_decision_checks(raw, canonical, payload):
    """Require explicit, consistent model judgments for all supplied prior chapters.

    Return None. Missing/foreign comparisons, omitted objective matches or
    contradictory blocker relationships raise; no judgment is silently corrected.
    Nonliteral semantic similarity remains the independent model's responsibility.
    """
    paired = decision_comparisons(payload)
    if payload.get("decision_comparisons") != paired:
        raise ValueError("Decision comparison context differs from current evidence")
    checks = raw["decision_checks"]
    cards = {card["id"]: card for card in paired["prior"]}
    if not isinstance(checks, dict) or set(checks) != set(cards):
        raise ValueError("Decision checks must cover every prior chapter exactly once")
    for identifier, relation in checks.items():
        if relation not in ("DISTINCT", "SAME_DECISION", "EXACT_COPY"):
            raise ValueError("Unknown decision comparison relation")
        card = cards[identifier]
        if card["same_formula"] and relation != "EXACT_COPY":
            raise ValueError("Decision check omitted an exact formula copy")
        if not card["same_formula"] and relation == "EXACT_COPY":
            raise ValueError("Decision check invented an exact formula copy")
        if not card["same_formula"] and card["identical_decision_and_action"] and relation != "SAME_DECISION":
            raise ValueError("Decision check missed identical business decision and action")
        blockers = [issue for issue in canonical["blocking_issues"]
                    if issue["category"] in ("EXACT_COPY", "DUPLICATE_DECISION")
                    and issue["evidence"].get("comparator_id") == identifier]
        expected = {"EXACT_COPY": "EXACT_COPY", "SAME_DECISION": "DUPLICATE_DECISION"}.get(relation)
        if expected and (not blockers or any(issue["category"] != expected for issue in blockers)):
            raise ValueError("Decision relationship requires its matching duplication blocker")
        if relation == "DISTINCT" and blockers:
            raise ValueError("Distinct decision contradicts a duplication blocker")


def evidence_catalog(payload):
    """Index exact supplied fields/sentences, returning a deterministic typed map.

    Input is an allowlisted review payload. IDs bind kind, owner, field and text;
    a changed passage cannot inherit an old ID. Missing comparison evidence raises
    before inference. No paraphrasing, external lookup or semantic labels occur.
    """
    catalog = {}

    def add(kind, field, owner, text, scope="whole"):
        """Register one exact string; return its ID or None for an absent string.
        Hash collisions raise; inspect the original payload rather than guessing.
        """
        if not isinstance(text, str) or not text.strip():
            return None
        row = {"kind": kind, "field": field, "owner_id": owner, "text": text, "scope": scope}
        encoded = json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
        key = kind[0].upper() + hashlib.sha256(encoded).hexdigest()[:12]
        if key in catalog and catalog[key] != row:
            raise ValueError("Evidence reference collision")
        catalog[key] = row
        return key

    draft = payload["current_draft"]
    for field in ("new_sutra", "grammar_mr", "translation_mr", "title_mr", "application_mr",
                  "action_mr", "summary_mr"):
        add("draft", field, None, draft.get(field))
    for field in ("exposition", "dos_mr", "donts_mr"):
        for index, text in enumerate(draft.get(field, [])):
            add("draft", f"{field}.{index}", None, text)
    for pair in payload["00_review_checks"]["source_claim_pairs"]:
        add("draft", pair["field"], pair["source_id"], pair["current_claim"])
        # Split only comparison prose; full paragraphs remain selectable too.
        for sentence in re.split(r"(?<=[।.!?])\s+", pair["current_claim"]):
            add("draft", pair["field"], pair["source_id"], sentence, "sentence")
    for pair in payload["00_review_checks"]["case_fact_pairs"]:
        add("draft", pair["field"], pair["case_id"], pair["current_text"])
    for source in payload["canonical_sources"]["references"]:
        for field in ("original_text", "meaning_mr"):
            add("source", field, source["id"], source.get(field))
    for case in payload["canonical_sources"]["examples"]:
        add("case", "text_mr", case["case_id"], case.get("text_mr"))
    return catalog


def evidence_selection(payload):
    """Return the catalog plus comparison-specific permitted ID menus.

    Input is a clean payload; unresolved sources raise before any provider call.
    Menus express ownership, not expected classifications or approval labels.
    """
    catalog = evidence_catalog(payload)
    comparisons = []
    for pair in payload["00_review_checks"]["source_claim_pairs"]:
        refs = [key for key, row in catalog.items() if row["kind"] == "draft" and row["field"] == pair["field"]]
        whole = [key for key in refs if catalog[key]["scope"] == "whole"]
        sources = [key for key, row in catalog.items() if row["kind"] == "source" and row["owner_id"] == pair["source_id"]]
        if len(whole) != 1 or not sources:
            raise ValueError("Comparison lacks current draft or canonical source evidence")
        comparisons.append({"comparison_ref": whole[0], "draft_refs": refs, "source_refs": sources})
    return {"catalog": catalog, "comparisons": comparisons}


def materialize_review(raw, payload):
    """Resolve a reference-only model answer into the existing review contract.

    Return (canonical response, selection audit). Unknown, stale, cross-type,
    cross-field or cross-source references raise. All quotes come from supplied
    text; outcome, categories, reasons and questions remain the model's choices.
    The caller MUST apply validate_review afterward; this function never passes
    a draft or supplies missing objections. Raw provider responses remain intact.
    """
    expected = {"decision_checks", "source_checks", "outcome", "blocking_issues", "advisory_notes", "uncertainties"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError("Reference review requires exactly six root fields")
    selection = evidence_selection(payload)
    if payload.get("evidence_selection") != selection:
        raise ValueError("Evidence catalog differs from immutable payload text")
    catalog = selection["catalog"]
    allowed_comparisons = {row["comparison_ref"]: row for row in selection["comparisons"]}
    audit = []

    def resolve(ref, kind, path):
        """Resolve one typed ID and log selection; invalid IDs never fall back to text."""
        if not isinstance(ref, str) or ref not in catalog or catalog[ref]["kind"] != kind:
            raise ValueError("Unknown or wrong-kind evidence reference")
        audit.append({"response_path": path, "ref": ref})
        return catalog[ref]

    def exact_keys(value, keys):
        """Reject generated quote fields, missing identifiers and unexpected schema keys."""
        if not isinstance(value, dict) or set(value) != set(keys):
            raise ValueError("Reference record has missing or unexpected fields")

    for field in ("source_checks", "blocking_issues", "uncertainties"):
        if not isinstance(raw[field], list):
            raise ValueError("Reference review evidence sections must be lists")
    result = {"source_checks": [], "outcome": raw["outcome"], "blocking_issues": [],
              "advisory_notes": deepcopy(raw["advisory_notes"]), "uncertainties": []}
    for index, check in enumerate(raw["source_checks"]):
        exact_keys(check, ("comparison_ref", "source_claim_ref", "application_ref", "source_ref", "classification", "reason"))
        menu = allowed_comparisons.get(check["comparison_ref"]) if isinstance(check["comparison_ref"], str) else None
        if menu is None:
            raise ValueError("Source check must select a whole current comparison")
        current = resolve(check["comparison_ref"], "draft", f"source_checks.{index}.comparison_ref")
        source = resolve(check["source_ref"], "source", f"source_checks.{index}.source_ref")
        if check["source_ref"] not in menu["source_refs"]:
            raise ValueError("Source check selected another comparison's source")
        quotes = {}
        for field in ("source_claim_ref", "application_ref"):
            ref = check[field]
            if ref is None:
                quotes[field] = ""
                continue
            row = resolve(ref, "draft", f"source_checks.{index}.{field}")
            if ref not in menu["draft_refs"]:
                raise ValueError("Source check selected text from another draft field")
            quotes[field] = row["text"]
        result["source_checks"].append({"field": current["field"], "source_id": source["owner_id"],
            "source_claim_quote": quotes["source_claim_ref"], "application_quote": quotes["application_ref"],
            "source_quote": source["text"], "classification": check["classification"], "reason": check["reason"]})
    for index, issue in enumerate(raw["blocking_issues"]):
        exact_keys(issue, ("category", "draft_ref", "reason", "evidence"))
        current = resolve(issue["draft_ref"], "draft", f"blocking_issues.{index}.draft_ref")
        ev = deepcopy(issue["evidence"])
        if not isinstance(ev, dict):
            raise ValueError("Reference blocker evidence must be an object")
        category = issue["category"]
        if category == "EXACT_COPY" and current["field"] != "new_sutra":
            raise ValueError("Exact-copy evidence must select the current formula")
        if category == "DUPLICATE_DECISION" and current["field"] not in {"summary_mr", "action_mr", "new_sutra"}:
            raise ValueError("Duplicated decision evidence must select its summary, action or formula")
        if category == "MECHANICAL":
            rule = ev.get("rule")
            if rule in {"word_limit", "character_limit"} and current["field"] != "new_sutra":
                raise ValueError("Formula limit evidence must select the current formula")
            if rule == "exposition_minimum" and not current["field"].startswith("exposition."):
                raise ValueError("Exposition limit evidence must select an exposition paragraph")
        if category == "SOURCE_DISTORTION":
            exact_keys(ev, ("source_ref",))
            source = resolve(ev["source_ref"], "source", f"blocking_issues.{index}.evidence.source_ref")
            if current["field"].startswith("comparative_mr.") and current["owner_id"] != source["owner_id"]:
                raise ValueError("Source blocker selected another comparison's source")
            ev = {"source_id": source["owner_id"], "source_quote": source["text"]}
        elif category == "CASE_FACT":
            if set(ev) == {"case_ref", "canonical_ref"}:
                # Some providers return the owner ID alongside its canonical ID.
                # Both were selected, and both must agree; never infer a missing ID.
                case = resolve(ev["canonical_ref"], "case", f"blocking_issues.{index}.evidence.canonical_ref")
                if ev["case_ref"] != case["owner_id"]:
                    raise ValueError("Selected case owner does not match canonical reference")
            else:
                exact_keys(ev, ("case_ref",))
                selected = ev["case_ref"]
                if isinstance(selected, str) and selected not in catalog:
                    matches = [key for key, row in catalog.items()
                               if row["kind"] == "case" and row["owner_id"] == selected]
                    if len(matches) != 1:
                        raise ValueError("Case identity must uniquely identify supplied canonical evidence")
                    case = resolve(matches[0], "case", f"blocking_issues.{index}.evidence.case_ref")
                    audit[-1]["selected_owner_id"] = selected
                else:
                    case = resolve(selected, "case", f"blocking_issues.{index}.evidence.case_ref")
            if not current["field"].startswith("examples.") or current["owner_id"] != case["owner_id"]:
                raise ValueError("Case blocker must select its matching current example")
            ev = {"case_id": case["owner_id"], "canonical_quote": case["text"]}
        else:
            fields = {"MECHANICAL": ("rule",), "EXACT_COPY": ("comparator_id",),
                      "DUPLICATE_DECISION": ("comparator_id",),
                      "GRAMMAR": ("rule", "explanation"), "UNSUPPORTED_CLAIM": ("claim_type", "explanation")}
            if category not in fields:
                raise ValueError("Unknown reference blocker category")
            exact_keys(ev, fields[category])
            if category == "DUPLICATE_DECISION":
                if ev["comparator_id"] not in {card["id"] for card in payload["comparison_chapters"]}:
                    raise ValueError("Unknown duplicated decision comparator")
                ev.update(same_decision=payload["current_draft"]["summary_mr"],
                          same_action=payload["current_draft"]["action_mr"])
        result["blocking_issues"].append({"category": category, "field": current["field"],
            "quote": current["text"], "reason": issue["reason"], "evidence": ev})
    for index, uncertain in enumerate(raw["uncertainties"]):
        exact_keys(uncertain, ("category", "draft_ref", "question"))
        current = resolve(uncertain["draft_ref"], "draft", f"uncertainties.{index}.draft_ref")
        result["uncertainties"].append({"category": uncertain["category"], "field": current["field"],
                                      "quote": current["text"], "question": uncertain["question"]})
    validate_decision_checks(raw, result, payload)
    return result, audit

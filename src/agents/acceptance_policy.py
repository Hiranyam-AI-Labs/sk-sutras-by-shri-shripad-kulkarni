"""Versioned, fail-closed acceptance policy for contemporary Udyam aphorisms.

Automated checks establish eligibility for scholarly review, never human approval.
Missing evidence remains NOT_EVALUATED. Legacy 13-gate scores have no authority.
"""

import re
from typing import Any, Dict, Iterable

from src.agents.validator_agent import ValidatorAgent


POLICY_VERSION = "udyam-15/1"
GATE_NAMES = (
    "short_formulation", "grammar_apparatus", "narada_fidelity",
    "shandilya_fidelity", "iks_grounding", "bhashya_length",
    "principal_cases", "yoga_application", "ethical_consistency",
    "originality", "substantive_pairing", "actionable_guidance",
    "canon_duplicates", "business_relevance", "example_diversity",
)


def evaluate_policy(
    chapter: Dict[str, Any], assessments: Dict[str, Dict[str, str]] | None = None,
    existing_sutras: Iterable[str] = (),
) -> Dict[str, Any]:
    """Evaluate a draft chapter and evidence supplied by the independent verifier.

    ``chapter`` is untrusted composition data; ``assessments`` maps gate names to
    {status, evidence} from a verifier. Returns all fifteen statuses and review
    eligibility. Malformed evidence remains NOT_EVALUATED; deterministic defects
    become FAIL. Inspect ``issues`` and gate names to debug without raw prompts.
    """
    assessments = assessments or {}
    gates = {name: "NOT_EVALUATED" for name in GATE_NAMES}
    issues = []
    for name in GATE_NAMES:
        item = assessments.get(name)
        if isinstance(item, dict) and item.get("status") in {"PASS", "FAIL", "HUMAN_REVIEW_REQUIRED"} and isinstance(item.get("evidence"), str) and item["evidence"].strip():
            gates[name] = item["status"]

    verse = chapter.get("original_sanskrit_verse", chapter.get("sanskrit", ""))
    words = re.findall(r"[^\s।॥]+", verse) if isinstance(verse, str) else []
    if 2 <= len(words) <= 5:
        if gates["short_formulation"] == "NOT_EVALUATED":
            gates["short_formulation"] = "PASS"
    else:
        gates["short_formulation"] = "FAIL"
    if not 2 <= len(words) <= 5:
        issues.append("Contemporary sutra must contain two to five displayed words.")

    for field in ("padaccheda", "anvaya", "nirukta", "translation_en", "translation_mr"):
        if not isinstance(chapter.get(field), str) or not chapter[field].strip():
            gates["grammar_apparatus"] = "FAIL"
            issues.append(f"Missing {field}.")

    commentary = chapter.get("comprehensive_bhashya_mr", chapter.get("detailed_commentary", ""))
    count = len(commentary.split()) if isinstance(commentary, str) else 0
    if 70 <= count <= 110:
        if gates["bhashya_length"] == "NOT_EVALUATED":
            gates["bhashya_length"] = "PASS"
    else:
        gates["bhashya_length"] = "FAIL"
    if not 70 <= count <= 110:
        issues.append(f"Marathi Bhashya has {count} whitespace-delimited words; required 70-110.")

    cases = chapter.get("biographical_case_studies")
    if (not isinstance(cases, list) or len(cases) != 2 or
            {case.get("region") for case in cases if isinstance(case, dict)} != {"EASTERN", "WESTERN"} or
            any(not isinstance(case, dict) or not case.get("person") or
                not case.get("business") or not case.get("provenance") for case in cases)):
        gates["principal_cases"] = "FAIL"
        issues.append("Exactly two sourced principal cases, one Eastern and one Western, are required.")
    guidance = chapter.get("dos_and_donts")
    if (not isinstance(guidance, dict) or
            not isinstance(guidance.get("dos"), list) or
            not isinstance(guidance.get("donts"), list) or
            len(guidance["dos"]) != 3 or len(guidance["donts"]) != 3):
        gates["actionable_guidance"] = "FAIL"
        issues.append("Exactly three DOs and three DONTs required.")

    business = chapter.get("business_assessment")
    if (not isinstance(business, dict) or
            any(not isinstance(business.get(key), str) or not business[key].strip()
                for key in ("context", "reader", "decision", "action", "source_rationale"))):
        gates["business_relevance"] = "FAIL"
        issues.append("Business context, reader, decision, action and source rationale required.")

    canon = list(existing_sutras)
    if canon and isinstance(verse, str):
        duplicate, match, _ = ValidatorAgent.check_duplicate_or_near_duplicate(verse, canon)
        if duplicate:
            gates["canon_duplicates"] = "FAIL"
            issues.append(f"Duplicate formulation in existing canon: {match}")
    if any(status == "FAIL" for status in gates.values()):
        status = "NEEDS_REVISION"
    elif all(status == "PASS" for status in gates.values()):
        status = "AI_VALIDATED_FOR_HUMAN_REVIEW"
    else:
        status = "HUMAN_REVIEW_REQUIRED"
    return {"policy_version": POLICY_VERSION, "gates": gates, "issues": issues,
            "overall_status": status, "passed_count": sum(v == "PASS" for v in gates.values()),
            "commentary_word_count": count}

"""Export only saved, independently assessed entries into the protected V19 design."""

import argparse
import json
from copy import deepcopy
from pathlib import Path

from src.doc_export.research_book import render_research_book
from src.orchestration.research_acceptance import assess_research_entry
from src.orchestration.independent_review import canonical_hash

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "logs/author-research-generation-20261118"


def apply_editorial_corrections(entry, corrections):
    """Apply reviewed literal prose corrections while preserving raw API output.

    Returns a deep copy; missing/ambiguous old text or protected fields raise.
    The ledger records post-model editorial changes, not a new validator verdict.
    Debug exact field paths and source-supported replacement text before retry.
    """
    value = deepcopy(entry)
    allowed = {"grammar_mr", "translation_mr", "exposition", "comparative_mr",
               "application_mr", "action_mr", "summary_mr", "dos_mr", "donts_mr"}
    for correction in corrections:
        parts = correction["field"].split(".")
        if parts[0] not in allowed or not correction.get("reason"):
            raise ValueError("Editorial correction targets a protected or unreasoned field")
        container = value
        for part in parts[:-1]:
            container = container[int(part)] if isinstance(container, list) else container[part]
        key = int(parts[-1]) if isinstance(container, list) else parts[-1]
        old, new = correction["old"], correction["new"]
        if not old or not new or not isinstance(container[key], str) or container[key].count(old) != 1:
            raise ValueError("Editorial correction must match exactly once")
        container[key] = container[key].replace(old, new, 1)
    return value


def select_reviewed_draft(result, corrections):
    """Select export/audit prose without changing a hash-bound reviewed draft.

    Params: saved result and this entry's legacy literal corrections. Return:
    independent draft copy. V2 binding fields require a typed READY review,
    exact canonical draft hash and rubric identity; invalid bindings raise
    ValueError and never fall back to legacy overlays. Legacy results retain
    existing overlay validation/errors. No inputs, ledgers or reviews are edited.
    """
    draft, review = result["draft"], result["review"]
    binding_fields = {"typed_review", "reviewed_draft_sha256", "rubric_sha256"}
    if binding_fields.intersection(review):
        typed = review.get("typed_review")
        if not isinstance(typed, dict):
            raise ValueError("V2 review requires typed_review; legacy fallback forbidden")
        if review.get("reviewed_draft_sha256") != canonical_hash(draft):
            raise ValueError("V2 reviewed draft hash mismatch")
        rubric = review.get("rubric_sha256")
        if (not isinstance(rubric, str) or len(rubric) != 64
                or any(c not in "0123456789abcdef" for c in rubric)):
            raise ValueError("V2 review requires a rubric SHA256 identity")
        if (review.get("verdict") != "PASS" or typed.get("outcome") != "READY"
                or typed.get("blocking_issues") != [] or typed.get("uncertainties") != []):
            raise ValueError("V2 typed review is held or inconsistent with PASS")
        return deepcopy(draft)
    return apply_editorial_corrections(draft, corrections)


def review_selection_evidence(result, corrections, selected):
    """Describe a successfully selected draft before display renumbering.

    Params: saved result, entry corrections and select_reviewed_draft output.
    Return: JSON-ready provenance, including actual legacy overlay count. Hash
    serialization/key errors propagate; call only after selection succeeds.
    Rubric identity is recorded, not certified against a changing current rubric.
    """
    review = result["review"]
    bound = "typed_review" in review
    return {"mode": "v2_hash_bound" if bound else "legacy_export_overlay",
            "saved_draft_sha256": canonical_hash(result["draft"]),
            "selected_draft_sha256": canonical_hash(selected),
            "reviewed_draft_sha256": review.get("reviewed_draft_sha256") if bound else None,
            "rubric_sha256": review.get("rubric_sha256") if bound else None,
            "review_binding_verified": bound,
            "editorial_overlay_count": 0 if bound else len(corrections),
            "post_review_prose_changed": selected != result["draft"]}


def export(output, target, allow_exclusions=False):
    """Render accepted entries1..target without paid calls or overwriting outputs.

    Inputs: new DOCX path and positive target; returns preservation report.
    Missing/review-failed records raise before export. Inspect entry JSON and
    source catalog to diagnose provenance errors; author approval stays pending.
    """
    if type(target) is not int or target < 1:
        raise ValueError("Positive entry target required")
    catalog = json.loads((WORK / "source_catalog.json").read_text(encoding="utf-8"))
    plan = json.loads((WORK / "plan.json").read_text(encoding="utf-8"))
    references = {record["id"]: record for record in catalog["references"]}
    references["CMP008"].update(title_mr="स्वातंत्र्याविषयी", author_mr="जॉन स्टुअर्ट मिल",
                                locator_mr="प्रकरण २ — विचार आणि चर्चेचे स्वातंत्र्य")
    display_path = WORK / "source_display_mr.json"
    if display_path.exists():
        for source_id, labels in json.loads(display_path.read_text(encoding="utf-8")).items():
            if source_id not in references or set(labels) != {"title_mr", "author_mr", "locator_mr"}:
                raise ValueError("Display overlay may only localize known reference labels")
            references[source_id].update(labels)
    proposed = [{"id": f"proposed:{item['id']}", "title": item["title"]}
                for group in catalog["groups"] for item in group["items"]
                if item["status"] == "requested_not_consulted"]
    correction_path = WORK / "editorial_corrections.json"
    corrections = json.loads(correction_path.read_text(encoding="utf-8")) if correction_path.exists() else {}
    entries, prior, used, excluded, numbering = [], [], set(), [], []
    selections, applied_corrections = {}, {}
    for number in range(1, target + 1):
        result = json.loads((WORK / f"entry-{number:03d}.json").read_text(encoding="utf-8"))
        if (result["status"] != "READY_FOR_AUTHOR_REVIEW" or
                result["assessment"]["status"] != "PASS" or result["review"]["verdict"] != "PASS"):
            if not allow_exclusions:
                raise ValueError(f"Entry{number} has unresolved acceptance findings")
            excluded.append({"source_number": number, "id": result["draft"]["id"],
                             "assessment": result["assessment"], "review": result["review"]})
            continue
        entry_corrections = corrections.get(result["draft"]["id"], [])
        draft = select_reviewed_draft(result, entry_corrections)
        selections[draft["id"]] = review_selection_evidence(result, entry_corrections, draft)
        if selections[draft["id"]]["mode"] == "legacy_export_overlay" and draft["id"] in corrections:
            applied_corrections[draft["id"]] = deepcopy(entry_corrections)
        assessment = assess_research_entry(draft, plan["entries"][number-1]["source_packet"], prior, [], used)
        if assessment["status"] != "PASS":
            raise ValueError(f"Exported entry{number} failed structural reassessment: {assessment['issues']}")
        display_number = len(entries) + 1
        numbering.append({"id": draft["id"], "source_number": number, "display_number": display_number})
        draft["number"] = display_number
        entries.append(draft)
        prior.append(draft["new_sutra"])
        used.update(case["case_id"] for case in draft["examples"])
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report = render_research_book(
        Path("C:/Users/LENOVO/Downloads/SK_Sutras/17Nov2026/Udyam_Sutre_Sampurna_Granth_v19.docx"),
        Path("C:/Users/LENOVO/Downloads/SK_Sutras/Udyam_Sutre_Sampurna_Mukha_Anukramanika_Malaprushtha-v2.docx"),
        entries, plan["chapters"], references, output, proposed)
    report["post_model_editorial_corrections"] = applied_corrections
    report["review_selections"] = selections
    report["editorial_review_note"] = (
        "V2 selections preserve exact hash-bound reviewed drafts; no editorial ledger is reapplied. "
        "Listed post-model corrections apply only to legacy selections and were structurally reassessed, "
        "not independently re-reviewed here. Selection hashes precede display-only renumbering in "
        "numbering_map; source drafts and reviews remain unchanged. Author review pending.")
    report["excluded_from_book"] = excluded
    report["numbering_map"] = numbering
    (WORK / f"export-{target}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-exclusions", action="store_true")
    args = parser.parse_args()
    print(json.dumps(export(args.output, args.target, args.allow_exclusions), ensure_ascii=False, indent=2))

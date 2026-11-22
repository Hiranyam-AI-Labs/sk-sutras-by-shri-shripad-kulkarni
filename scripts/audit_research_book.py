"""Offline final-book audit; structural checks are not author/scholar approval.

Read saved results through a source number, use the export helper's reviewed selection,
and assess only READY + assessment PASS + independent review PASS candidates.
Missing files mean an incomplete final audit, not a generation-stop instruction.
CLI: python scripts/audit_research_book.py --through 100 --output logs/.../audit.json
Only the explicit report destination is written. No runner/provider/render calls.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_research_book import select_reviewed_draft, review_selection_evidence
from src.orchestration.research_acceptance import (
    REFERENCE_FIELDS, _devanagari_word, _normalize_formula, assess_research_entry,
)

WORK = ROOT / "logs/author-research-generation-20261118"
CASES = ROOT / "logs/author-hybrid-book-20261117"
MODERN = {"CMP012", "CMP013", "CMP014"}
AMBIGUOUS = {"apple", "target", "shell", "next", "meta", "zoom", "gore", "king", "foundation"}
PROSE_FIELDS = ("title_mr", "new_sutra", "grammar_mr", "translation_mr", "exposition",
                "dos_mr", "donts_mr", "application_mr", "action_mr", "summary_mr")


def _read(path):
    """Read UTF-8 JSON. Param: path. Return: decoded data. I/O/JSON errors
    propagate to the audit's diagnostics; debug the named input, never edit it.
    """
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _fold(text):
    """Normalize a name for literal matching. Param: text; return: folded text.
    No transliteration or semantic identity inference; debug unmatched spellings.
    """
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _prose(entry):
    """Yield (field path, text) for reader prose, including immutable case prose.
    Param: entry; return: iterator. Malformed optional fields are skipped here;
    structural acceptance handles them. Source metadata is deliberately excluded.
    """
    for field in PROSE_FIELDS:
        value = entry.get(field)
        if isinstance(value, str):
            yield field, value
        elif isinstance(value, list):
            for index, text in enumerate(value):
                if isinstance(text, str):
                    yield f"{field}.{index}", text
    for field, key in (("comparative_mr", "explanation_mr"), ("examples", "text_mr")):
        for index, item in enumerate(entry.get(field, [])):
            if isinstance(item, dict) and isinstance(item.get(key), str):
                yield f"{field}.{index}.{key}", item[key]


def _review_flags(entries, plan_entries, old_cases, references, numbering, excluded_numbers=()):
    """Find review-only repetition/mention/numbering signals.
    Params: accepted drafts, plan rows, old cases, ledger and numbering map.
    Return: flags. Literal aliases only; no automatic rejection or inferred guilt.
    Debug: each flag contains entry IDs, field paths and matched evidence.
    """
    flags, aliases = [], collections.defaultdict(set)
    owners = {e["source_entry_id"]: e["id"] for e in plan_entries}
    own_sources = {e["id"]: e["source_entry_id"] for e in plan_entries}
    philosophers = {_fold(r["author"]) for r in references.values()}
    for case in old_cases:
        for name in [case.get("entity", ""), *case.get("aliases", [])]:
            if not isinstance(name, str):
                continue
            name = _fold(name)
            letters = sum(unicodedata.category(c)[0] in {"L", "N"} for c in name)
            if letters < 5 or name in AMBIGUOUS or name in philosophers:
                continue
            aliases[name].add(case["entry_id"])
    patterns = [(name, re.compile(r"(?<![\w\u0900-\u097f])" + re.escape(name)
                                 + r"(?![\w\u0900-\u097f])"), source_ids)
                for name, source_ids in sorted(aliases.items())]
    paragraphs = collections.defaultdict(list)
    display = {r["source_number"]: r["display_number"] for r in numbering}
    renumbered = bool(excluded_numbers) or any(k != v for k, v in display.items())
    number_pattern = re.compile(
        r"(?:उद्यम\s*सूत्र|उद्यमसूत्र|सूत्र|नोंद|\bentry\b|\bsutra\b)\s*"
        r"(?:(?:क्रमांक|क्र\.?|नं\.?|number|no\.?|#)\s*)?([0-9०-९]+)"
        r"|\bNEW-([0-9]{3})\b", re.IGNORECASE)
    classical = re.compile(r"नारद|शा[ंण]डिल्य|शाण्डिल्य|पत[ंञ]जलि|पतञ्जलि|योग|गीता|ब्रह्म|"
                           r"narada|shandilya|patanjali|yoga|gita", re.IGNORECASE)
    for entry in entries:
        for field, text in _prose(entry):
            folded = _fold(text)
            for name, pattern, source_ids in patterns:
                if own_sources.get(entry["id"]) in source_ids:
                    continue
                if pattern.search(folded):
                    flags.append({"code": "other_business_mention", "entry_id": entry["id"],
                        "field": field, "matched_alias": name,
                        "other_entry_ids": sorted({owners[s] for s in source_ids if s in owners}),
                        "old_source_entry_ids": sorted(source_ids),
                        "note": "Known other business/person alias; context review only, not automatic case reuse."})
            if renumbered:
                for match in number_pattern.finditer(text):
                    prefix = text[max(0, match.start() - 32):match.start()]
                    if classical.search(prefix):
                        continue
                    source_number = int(match.group(1) or match.group(2))
                    if display.get(source_number) != source_number:
                        flags.append({"code": "possible_old_entry_number", "entry_id": entry["id"],
                            "field": field, "matched_text": match.group(0),
                            "source_number": source_number, "display_number": display.get(source_number),
                            "note": "Check whether this is an old book-entry reference; classical citations need not be renumbered."})
        for index, paragraph in enumerate(entry.get("exposition", [])):
            if isinstance(paragraph, str) and len(paragraph.split()) >= 30:
                paragraphs[" ".join(paragraph.split())].append((entry["id"], index))
    for text, locations in paragraphs.items():
        if len({item[0] for item in locations}) > 1:
            flags.append({"code": "repeated_exposition_paragraph",
                "entry_ids": sorted({item[0] for item in locations}), "locations": locations,
                "word_count": len(text.split()), "excerpt": text[:240],
                "note": "Exact text after whitespace normalization; review only."})
    return flags


def audit_book(work=WORK, through=100, cases_dir=CASES):
    """Audit one proposed final selection without writing.
    Params: work directory, positive final source number, old cases directory.
    Return: JSON-ready report with structural PASS/FAIL and separate review flags.
    Missing/malformed evidence fails closed; nonpassing saved verdicts are excluded.
    Debug: errors name files/entries. PASS never approves facts, language or author intent.
    """
    if type(through) is not int or through < 1:
        raise ValueError("--through must be a positive integer")
    work, cases_dir = Path(work), Path(cases_dir)
    report = {"structural_status": "FAIL", "author_approval": "PENDING",
        "scope": "Offline final-book QA, not a current generation gate",
        "through": through, "included": [], "excluded": [], "missing": [],
        "errors": [], "review_flags": [], "numbering_map": [], "review_selections": {},
        "limitations": [
            "Saved PASS verdicts are eligibility only; selected prose is reassessed locally.",
            "V2 draft hashes bind exact reviewed prose; legacy overlays are post-review changes, not a new independent review.",
            "Selection hashes precede display-only renumbering; rubric identities are recorded, not re-certified.",
            "Devanagari token counts do not certify Marathi, Sanskrit grammar or factual accuracy.",
            "Business aliases are literal, with short/ambiguous labels ignored; no inferred transliteration.",
            "Philosopher repetition is not business-case reuse. Semantic plagiarism is not tested.",
            "English original-quotation suppression and appendix quote-once rendering are delegated to the renderer.",
            "Review flags do not automatically reject an entry or confer author approval.",
        ]}
    errors = report["errors"]
    try:
        plan = _read(work / "plan.json")
        ledger = _read(work / "source_catalog.json")
        forbidden = _read(work / "forbidden_formulas.json")
        if isinstance(forbidden, dict):
            forbidden = forbidden["formulas"]
        if not isinstance(forbidden, list) or not forbidden or any(
                not isinstance(x, str) or not x.strip() for x in forbidden):
            raise ValueError("forbidden formulas must be a nonempty list of nonempty strings")
        plan_entries = plan["entries"]
        briefs = {e["number"]: e for e in plan_entries}
        if len(briefs) != len(plan_entries) or len({e["id"] for e in plan_entries}) != len(plan_entries):
            raise ValueError("Duplicate plan numbers or IDs")
        references = {r["id"]: r for r in ledger["references"]}
        if not references or len(references) != len(ledger["references"]):
            raise ValueError("Empty/duplicate source ledger")
        forbidden_normal = {_normalize_formula(x) for x in forbidden}
        for source_id, reference in references.items():
            if any(not isinstance(reference.get(k), str) or not reference[k].strip() for k in REFERENCE_FIELDS):
                raise ValueError(f"Incomplete canonical source ledger: {source_id}")
            for line in [reference["original_text"], *reference["original_text"].splitlines()]:
                if line.strip() and _normalize_formula(line) not in forbidden_normal:
                    errors.append({"code": "source_line_not_forbidden", "source_id": source_id,
                                   "detail": "Canonical source passage/line missing from forbidden ledger"})
        correction_path = work / "editorial_corrections.json"
        corrections = _read(correction_path) if correction_path.exists() else {}
        if not isinstance(corrections, dict):
            raise ValueError("Editorial correction ledger must be an object")
        files = sorted(cases_dir.glob("cases-[0-9]*.json"))
        if not files:
            raise ValueError(f"No old case alias files found in {cases_dir}")
        old_cases = [c for path in files for c in _read(path)]
        if not old_cases:
            raise ValueError("Old case alias files contain no records")
        for case in old_cases:
            if (not isinstance(case, dict) or not all(isinstance(case.get(k), str) and case[k]
                    for k in ("entry_id", "kind", "entity"))
                    or not isinstance(case.get("aliases", []), list)):
                raise ValueError("Malformed old case alias record")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append({"code": "input_error", "detail": str(exc)})
        return report
    old_case_index = {(c["entry_id"], c["kind"]): c for c in old_cases}
    if len(old_case_index) != len(old_cases):
        errors.append({"code": "duplicate_old_case", "detail": "Ambiguous canonical case lookup"})
        return report
    entries, prior, used_cases, used_entities = [], [], set(), {}
    modern_usage = collections.defaultdict(list)
    for number in range(1, through + 1):
        path = work / f"entry-{number:03d}.json"
        if number not in briefs:
            errors.append({"code": "missing_plan_entry", "source_number": number})
            continue
        if not path.exists():
            report["missing"].append(number)
            continue
        try:
            result = _read(path)
            if not isinstance(result, dict):
                raise ValueError("Saved result must be an object")
            if (result.get("status") != "READY_FOR_AUTHOR_REVIEW"
                    or result.get("assessment", {}).get("status") != "PASS"
                    or result.get("review", {}).get("verdict") != "PASS"):
                report["excluded"].append({"source_number": number, "id": briefs[number]["id"],
                    "status": result.get("status"), "reason": "Saved readiness/assessment/review gate did not pass"})
                continue
            brief, start_errors = briefs[number], len(errors)
            packet = brief["source_packet"]
            packet_hash = hashlib.sha256(json.dumps(packet, ensure_ascii=False, sort_keys=True,
                                        separators=(",", ":")).encode("utf-8")).hexdigest()
            if packet_hash != brief.get("source_packet_sha256"):
                raise ValueError("Frozen source-packet hash mismatch")
            for ref in packet["references"]:
                canonical = references.get(ref["id"])
                if canonical is None or any(ref.get(k) != canonical.get(k) for k in REFERENCE_FIELDS):
                    raise ValueError(f"Packet reference differs from source ledger: {ref.get('id')}")
            for case in packet["examples"]:
                original = old_case_index.get((brief["source_entry_id"], case["kind"]))
                if (original is None or case["case_id"] != f"{brief['source_entry_id']}-{case['kind']}"
                        or any(case.get(k) != original.get(k) for k in
                               ("kind", "entity", "text_mr", "url", "source_title"))):
                    raise ValueError(f"Packet case differs from old case ledger: {case.get('case_id')}")
            raw = result["draft"]
            if any(raw.get(k) != brief[k] for k in ("id", "number", "chapter")):
                raise ValueError("Draft identity/number/chapter does not match plan")
            entry_corrections = corrections.get(raw["id"], [])
            draft = select_reviewed_draft(result, entry_corrections)
            selection = review_selection_evidence(result, entry_corrections, draft)
            report["review_selections"][draft["id"]] = selection
            assessment = assess_research_entry(draft, packet, prior, forbidden, used_cases)
            for issue in assessment["issues"]:
                errors.append({"code": "entry_acceptance", "entry_id": draft["id"], "detail": issue})
            if result["assessment"].get("issues") or result["review"].get("issues"):
                errors.append({"code": "inconsistent_saved_pass", "entry_id": draft["id"]})
            expected_cases = [c["case_id"] for c in packet["examples"]]
            if draft.get("case_ids", expected_cases) != expected_cases:
                errors.append({"code": "case_selection_order", "entry_id": draft["id"]})
            comparison_counts = {}
            for comparison in draft.get("comparative_mr", []):
                source_id, text = comparison["source_id"], comparison["explanation_mr"]
                words = len(text.split())
                comparison_counts[source_id] = words
                if words >= 100:
                    errors.append({"code": "comparison_word_limit", "entry_id": draft["id"],
                                   "source_id": source_id, "words": words, "maximum": 99})
            chosen_modern = (set(draft.get("references", [])) | set(comparison_counts)) & MODERN
            for source_id in chosen_modern:
                modern_usage[source_id].append(draft["id"])
            for case in draft.get("examples", []):
                entity_key = re.sub(r"[\W_]+", "", _fold(case["entity"]))
                if entity_key in used_entities:
                    errors.append({"code": "duplicate_case_entity", "entry_id": draft["id"],
                                   "entity": case["entity"], "other_entry_id": used_entities[entity_key]})
                used_entities[entity_key] = draft["id"]
                used_cases.add(case["case_id"])
            prior.append(draft["new_sutra"])
            entries.append(draft)
            report["numbering_map"].append({"id": draft["id"], "source_number": number,
                                            "display_number": len(entries)})
            report["included"].append({"id": draft["id"], "source_number": number,
                "display_number": len(entries), "structural_status": "PASS" if len(errors) == start_errors else "FAIL",
                "devanagari_exposition_words": sum(_devanagari_word(t) for p in draft["exposition"] for t in p.split()),
                "comparison_words": comparison_counts,
                "editorial_overlay_count": selection["editorial_overlay_count"]})
        except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            errors.append({"code": "entry_error", "source_number": number, "detail": str(exc)})
    if report["missing"]:
        errors.append({"code": "incomplete_final_range", "missing_source_numbers": report["missing"]})
    if not entries:
        errors.append({"code": "empty_final_selection"})
    for source_id, ids in sorted(modern_usage.items()):
        if len(ids) > 1:
            errors.append({"code": "modern_source_reused", "source_id": source_id, "entry_ids": ids})
    report["modern_source_usage"] = {key: modern_usage.get(key, []) for key in sorted(MODERN)}
    try:
        report["review_flags"] = _review_flags(entries, plan_entries, old_cases, references, report["numbering_map"],
                                                [e["source_number"] for e in report["excluded"]])
    except (TypeError, KeyError, ValueError) as exc:
        errors.append({"code": "review_scan_error", "detail": str(exc)})
    report["counts"] = {"included": len(entries), "excluded": len(report["excluded"]),
        "missing": len(report["missing"]), "case_ids": len(used_cases), "entities": len(used_entities),
        "review_flags": len(report["review_flags"])}
    report["structural_status"] = "FAIL" if errors else "PASS"
    return report


def main(argv=None):
    """Run explicit final QA and write only its report under repository logs.
    Params: CLI argv; return: 0 for structural PASS, 1 for FAIL. Invalid output
    paths raise before writing; debug report.errors. Never call the paid runner.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", type=int, default=100)
    parser.add_argument("--work-dir", type=Path, default=WORK)
    parser.add_argument("--cases-dir", type=Path, default=CASES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    destination = args.output.resolve()
    logs = (ROOT / "logs").resolve()
    if not destination.is_relative_to(logs) or destination.suffix.lower() != ".json":
        parser.error("--output must be a JSON report beneath repository logs")
    if destination.exists():
        parser.error("--output already exists; choose a new audit report path")
    # Do not let a report destination become an input/correction/result file.
    if (destination.name in {"plan.json", "source_catalog.json", "forbidden_formulas.json",
                             "editorial_corrections.json", "source_display_mr.json"}
            or re.match(r"(?:entry-\d+|cases-\d.*)\.json$", destination.name)):
        parser.error("--output is a protected input filename")
    report = audit_book(args.work_dir, args.through, args.cases_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"structural_status": report["structural_status"],
                      "review_flags": len(report["review_flags"]), "report": str(destination)}))
    return 0 if report["structural_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

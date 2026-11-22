"""Freeze ten offline validator probes; never call a provider or approve a book.

Expected labels and reasons are evaluator-only. Call model_input(fixture) and
send the shared RUBRIC separately; never serialize the whole fixture to a model.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_research_book import apply_editorial_corrections
from src.orchestration.research_acceptance import (
    _devanagari_word, _normalize_formula, assess_research_entry,
)
from src.orchestration.independent_review import (
    SYSTEM, CONTRACT, VERSION, build_payload, canonical_hash, contract_hash,
)

WORK = ROOT / "logs/author-research-generation-20261118"
RUBRIC = SYSTEM + "\n" + CONTRACT


def digest(value):
    """Return stable JSON SHA256 for value; non-serializable input raises TypeError.
    Used to debug frozen packets and payload drift, not to certify truth.
    """
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def model_input(fixture):
    """Return the authoritative opinion-blind build_payload result.
    Param: fixture dict; missing evidence raises KeyError. Labels, reasons, IDs
    and provenance stay evaluator-side. Debug callers that serialize whole rows.
    """
    return build_payload(fixture["draft"], fixture["sources"], fixture["comparators"])


def comparator(draft, identifier=None, formula=None):
    """Return decision evidence from a draft, optionally overriding ID/formula.
    Missing draft fields raise KeyError; synthetic comparator variants are marked
    in the evaluator reason, never substituted for historical source records.
    """
    return {"id": identifier or draft["id"], "formula": formula or draft["new_sutra"],
            "decision_mr": draft["summary_mr"], "action_mr": draft["action_mr"]}


def build_fixtures(drafts, packets, prior_drafts):
    """Build ten probes from corrected 001/005/008/009 and canonical packets.
    Params: dictionaries keyed by number, plus accepted prior draft list.
    Return: fixture list; fail on invalid positive structure or absent four-word
    probe. Does not mutate inputs. Debug numbered positive acceptance failures.
    """
    fixtures = []

    def add(draft, sources, comparisons, outcome, categories, reason, rules=None):
        fixtures.append({"id": f"VC2-{len(fixtures)+1:03}", "draft": deepcopy(draft),
            "sources": deepcopy(sources), "comparators": deepcopy(comparisons),
            "expected": {"outcome": outcome, "required_categories": categories},
            "reason": reason})
        if rules:
            fixtures[-1]["expected"]["required_rules"] = list(rules)

    for number in (1, 5, 8, 9):
        draft, packet = drafts[number], packets[number]
        result = assess_research_entry(draft, packet, [], [], set())
        if result["status"] != "PASS":
            raise ValueError(f"Positive {number:03} fails structure: {result['issues']}")
        comparisons = [comparator(d) for d in prior_drafts if d["number"] < number]
        add(draft, packet, comparisons, "READY", [], {
            1: "Saved accepted baseline with export prose overlay; technical baseline, not author approval.",
            5: "Chandra retains the dissent-and-alternatives draft unchanged: literal title words are not required in the formula. Four words are valid when within 32 characters.",
            8: "Corrected evidence-sufficiency stopping rule differs from customer-problem discovery; shared inquiry/evidence vocabulary alone is not duplication.",
            9: "Chandra restores the saved responsibility/equanimity formula and qualifies the prose. Attributed modern process/outcome review is allowed without claiming that ancient authors prescribed an operational method.",
        }[number])
    if not any(len(f["draft"]["new_sutra"].strip().strip("।॥").split()) == 4 for f in fixtures):
        raise ValueError("Positive inputs must include an actual four-word formula probe")

    base, packet = drafts[1], packets[1]
    add(base, packet, [comparator(base, "PRIOR-001")], "REVISION_REQUIRED",
        ["EXACT_COPY"], "Synthetic prior comparator freezes the same formula and decision; exact copying must fail even when the draft otherwise reads well.")

    false_source = deepcopy(base)
    comparison = next((c for c in false_source["comparative_mr"] if c["source_id"] == "CMP008"), None)
    if comparison is None or not any(r["id"] == "CMP008" for r in packet["references"]):
        raise ValueError("Baseline needs its known Mill CMP008 source for attribution probe")
    comparison["explanation_mr"] = ("जॉन स्टुअर्ट मिल यांनी ऑन लिबर्टीमध्ये प्रत्येक उद्योगाने "
        "ग्राहकांची मुलाखत घेतल्यानंतर चोवीस तासांत नवीन उत्पादन बाजारात आणावे, "
        "असा स्पष्ट व्यावसायिक नियम दिला आहे.")
    add(false_source, packet, [], "REVISION_REQUIRED", ["SOURCE_DISTORTION"],
        "Controlled false claim attributed to the existing Mill passage; canonical source ID/text stay unchanged.")

    invented = deepcopy(base)
    invented["examples"][0]["text_mr"] += " या संस्थेच्या प्रत्येक ग्राहकाला दरवर्षी हमखास दुप्पट उत्पन्न मिळाले."
    add(invented, packet, [], "REVISION_REQUIRED", ["CASE_FACT"],
        "Synthetic invented outcome appended only to draft case prose; immutable source packet remains the factual authority.")

    long_formula = deepcopy(base)
    long_formula["new_sutra"] = "ग्राहकव्यथापरीक्षणपूर्वकं निर्णयं कुर्यात्"
    assert len(long_formula["new_sutra"]) > 32 and len(long_formula["new_sutra"].split()) <= 4
    add(long_formula, packet, [], "REVISION_REQUIRED", ["MECHANICAL"],
        "Mechanical negative: over 32 characters despite an allowed word count; no need for speculative Sanskrit criticism.", ["character_limit"])

    short = deepcopy(base)
    tokens, count = [], 0
    for token in " ".join(base["exposition"]).split():
        tokens.append(token)
        count += _devanagari_word(token)
        if count == 499:
            break
    short["exposition"] = [" ".join(tokens)]
    add(short, packet, [], "REVISION_REQUIRED", ["MECHANICAL"],
        "Mechanical negative: exactly 499 Devanagari tokens, not a semantic rejection or request for padding.", ["exposition_minimum"])

    duplicate = comparator(base, "PRIOR-002", "ग्राहकदुःखं पृष्ट्वा परीक्षेत्")
    assert _normalize_formula(duplicate["formula"]) != _normalize_formula(base["new_sutra"])
    add(base, packet, [duplicate], "REVISION_REQUIRED", ["DUPLICATE_DECISION"],
        "Synthetic nonidentical-formula comparator deliberately repeats the same practical decision and exact exercise. Real decision duplication remains a defect despite different wording.")
    return fixtures


def _read(path):
    """Read UTF-8 JSON path; I/O/JSON errors propagate with path for debugging."""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def revised_drafts(document):
    """Extract full drafts from Chandra's number-keyed map or candidates list.
    Param: Chandra document; return number->draft. Missing/duplicate 005/008/009
    fails closed; no patch guessing or promotion of saved held drafts.
    """
    rows = document.get("candidates") if isinstance(document, dict) else None
    if isinstance(document, dict) and document and all(str(k).isdigit() for k in document):
        rows = []
        for key, row in document.items():
            if (not isinstance(row, dict) or not isinstance(row.get("draft"), dict)
                    or row["draft"].get("number") != int(key)):
                raise ValueError("Number-keyed candidate identity does not match its draft")
            rows.append(row)
    if not isinstance(rows, list):
        raise ValueError("Revision file requires a number-keyed map or candidates list of full drafts")
    result = {}
    for row in rows:
        draft = row.get("draft") if isinstance(row, dict) else None
        if not isinstance(draft, dict):
            raise ValueError("Each revision candidate must contain a full draft")
        number = draft.get("number")
        if number in result:
            raise ValueError(f"Duplicate revision candidate {number}")
        result[number] = deepcopy(draft)
    if not {5, 8, 9}.issubset(result):
        raise ValueError("Revision candidates 005/008/009 are required before finalizing")
    return result


def prepare(work=WORK):
    """Read frozen local inputs and return fixtures plus provenance manifest.
    Param: directory with saved entries, plan, overlay and revision candidates.
    Missing revisions or changed inputs raise; never run an API, modify sources,
    or silently treat stale held drafts as corrected. Inspect candidate structure.
    """
    work = Path(work).resolve()
    paths = [work / name for name in ("plan.json", "revision_candidates_v2.json")]
    paths += sorted(work.glob("entry-*.json"))
    overlay_path = work / "editorial_corrections.json"
    if overlay_path.exists():
        paths.append(overlay_path)
    captured = {p: p.read_bytes() for p in paths}
    plan = json.loads(captured[work / "plan.json"])
    revision_document = json.loads(captured[work / "revision_candidates_v2.json"])
    proposals = revised_drafts(revision_document)
    overlay = json.loads(captured[overlay_path]) if overlay_path in captured else {}
    saved = [json.loads(captured[p]) for p in paths if p.name.startswith("entry-")]
    raw_drafts = {r["draft"]["number"]: r["draft"] for r in saved}
    rows = revision_document.get("candidates", list(revision_document.values()))
    for row in rows:
        if "source_draft_sha256" in row:
            original = raw_drafts.get(row["draft"]["number"])
            if original is None or digest(original) != row["source_draft_sha256"]:
                raise ValueError("Revision source draft hash no longer matches saved input")
    accepted = [apply_editorial_corrections(r["draft"], overlay.get(r["draft"]["id"], []))
                for r in saved if r.get("status") == "READY_FOR_AUTHOR_REVIEW"
                and r.get("assessment", {}).get("status") == "PASS"
                and r.get("review", {}).get("verdict") == "PASS"]
    baseline = next((d for d in accepted if d["number"] == 1), None)
    if baseline is None:
        raise ValueError("Saved accepted baseline 001 required")
    drafts = {1: baseline, **{n: proposals[n] for n in (5, 8, 9)}}
    packets = {}
    for n, d in drafts.items():
        row = next(e for e in plan["entries"] if e["number"] == n)
        if any(d[k] != row[k] for k in ("id", "number", "chapter", "title_mr")):
            raise ValueError(f"Candidate {n} changes protected identity/title")
        if any(d.get(k) != raw_drafts[n].get(k) for k in ("references", "case_ids", "examples")):
            raise ValueError(f"Candidate {n} changes protected references/cases")
        packet = row["source_packet"]
        if digest(packet) != row["source_packet_sha256"]:
            raise ValueError(f"Packet {n} hash differs from frozen plan")
        packets[n] = packet
    fixtures = build_fixtures(drafts, packets, accepted)
    for p, original in captured.items():
        if p.read_bytes() != original:
            raise ValueError(f"Input changed while preparing fixtures: {p}")
    return {"version": "validator-calibration-v2", "purpose": "Technical calibration only; not author/scholar approval",
        "rubric": RUBRIC, "fixtures": fixtures,
        "manifest": {"planned_calls": len(fixtures), "calls_performed": 0,
            "expected_ready": 4, "expected_revision_required": 6,
            "label_handling": "Send rubric plus model_input(row) ONLY. Never send expected, reason, fixture ID or this manifest.",
            "omitted_probe": "Standalone Sanskrit verb defect omitted to avoid an uncertain grammar label; specialist review remains pending.",
            "input_sha256": {str(p): hashlib.sha256(raw).hexdigest() for p, raw in captured.items()},
            "contract_version": VERSION, "contract_sha256": contract_hash(),
            "fixture_set_sha256": canonical_hash(fixtures),
            "payload_sha256": {f["id"]: canonical_hash(model_input(f)) for f in fixtures}}}


def main(argv=None):
    """Prepare CLI fixtures and exclusively create requested calibration JSON.
    Params: argv; return 0. Missing candidates, invalid output or existing file
    fail without writes. Debug input paths; never overwrite plan or raw entries.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=WORK)
    parser.add_argument("--output", type=Path, default=WORK / "validator_calibration_v2.json")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / "logs").resolve()) or output.name != "validator_calibration_v2.json":
        parser.error("Output must be validator_calibration_v2.json beneath repository logs")
    if output.exists():
        parser.error("Frozen output already exists; do not overwrite")
    result = prepare(args.work_dir)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"fixtures": len(result["fixtures"]), "calls_performed": 0, "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

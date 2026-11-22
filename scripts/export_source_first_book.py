"""Offline export of explicit, hash-bound source-first result files.

No discovery, generation, content repair or API calls. Optional explicit Marathi
reference labels change presentation copies only. Each --result
may supply multiple paths and may be repeated. Their explicit order breaks ties
within the existing JOURNEY rank (growth/people/society share one rank).
Logical candidate numbers may have gaps. Only presentation number and chapter
change; canonical drafts, review bindings and complete result lineage survive
in the adjacent OUTPUT.qa.json receipt.

References: an explicit ID-keyed registry or list of exact eight-field records.
--reference-display may supply an ID-keyed map containing only title_mr,
author_mr, locator_mr and tradition_mr. Canonical records/quotes/URLs and review
bindings stay unchanged; the QA receipt records overlay bytes and label changes.
Final-book mode requires accepted opening and closure proposals. The explicit
--diagnostic-pilot flag relaxes only that boundary requirement. Both modes still
require every result to pass all review/proposal gates. Sutrakar's selected
proposal must carry journey_stage; no planning-brief or chapter inference.

The existing renderer owns protected-template preservation. This adapter checks
the approved preflight assets, then delegates unchanged content to that renderer.
Fresh Word/PDF rendering and visual QA remain NOT_RUN. Import performs no I/O.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_source_first_book import JOURNEY
from src.doc_export import research_book
from src.doc_export.research_book import render_research_book
from src.orchestration.independent_review import canonical_hash
from src.orchestration.research_acceptance import REFERENCE_FIELDS

DISPLAY_FIELDS = frozenset({"title_mr", "author_mr", "locator_mr", "tradition_mr"})
PREFLIGHT = ROOT / "logs/source-first-generation-20261120/book-export-preflight.json"
CHAPTER_TITLES = {
    1: "प्रारंभ", 2: "आचरण", 3: "विकास, सहकारी आणि समाज", 4: "समारोप",
}


def _require(condition, message):
    """Reject a malformed input before presentation/export; return None."""
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _positive_int(value):
    return type(value) is int and value > 0


def reference_registry(value):
    """Copy exact canonical records; reject duplicate IDs or inferred fields."""
    if isinstance(value, list):
        _require(all(isinstance(r, dict) and _text(r.get("id")) for r in value),
                 "Reference records need explicit IDs")
        _require(len({r["id"] for r in value}) == len(value), "Duplicate reference ID")
        value = {r["id"]: r for r in value}
    _require(isinstance(value, dict) and bool(value), "Explicit reference registry required")
    for ident, record in value.items():
        _require(_text(ident) and isinstance(record, dict)
                 and set(record) == set(REFERENCE_FIELDS),
                 "References require exactly the canonical eight fields")
        _require(record["id"] == ident and all(_text(v) for v in record.values()),
                 "Reference ID mismatch or blank canonical field")
        url = urlsplit(record["url"])
        _require(url.scheme in {"http", "https"} and bool(url.hostname)
                 and not url.username and not url.password
                 and not any(c.isspace() for c in record["url"]),
                 "Reference URL must be supplied HTTP(S)")
    return deepcopy(value)


def reference_display(registry, overlay):
    """Build separate display copies; return records and exact label-change audit.

    Inputs are a validated canonical registry and an explicit ID-keyed overlay.
    Reject unknown IDs/fields, blank values or malformed containers before any
    export. Never infer translations or modify canonical evidence/review data.
    """
    _require(isinstance(overlay, dict), "Reference display must be an ID-keyed object")
    display, changes = deepcopy(registry), []
    for ident, labels in overlay.items():
        _require(ident in registry, "Unknown reference display ID")
        _require(isinstance(labels, dict) and bool(labels)
                 and set(labels) <= DISPLAY_FIELDS,
                 "Reference display allows only title_mr/author_mr/locator_mr/tradition_mr")
        for field, value in labels.items():
            _require(_text(value), "Reference display labels must be nonblank strings")
            canonical_field = field[:-3]
            before = research_book._reference_label(registry[ident], canonical_field)
            display[ident][field] = value
            changes.append({"reference_id": ident, "field": field,
                            "canonical_value": registry[ident][canonical_field],
                            "before_display": before, "after_display": value,
                            "visible_text_changed": before != value})
    return display, {"overlay_canonical_sha256": canonical_hash(overlay),
                     "field_changes": changes,
                     "display_reference_records_sha256": canonical_hash(display),
                     "canonical_reference_records_changed": False,
                     "original_quotes_and_urls_changed": False,
                     "canonical_drafts_and_review_hashes_changed": False}


def _selected_proposal(container, number):
    """Select the exact logical candidate from a flat or batch Sutrakar proposal."""
    _require(isinstance(container, dict), "Missing Sutrakar proposal")
    if "proposals" in container:
        _require("decision" not in container, "Ambiguous flat and batch proposal")
        rows = container["proposals"]
        _require(isinstance(rows, list) and all(isinstance(p, dict)
                 and _positive_int(p.get("number")) for p in rows), "Malformed batch proposals")
        _require(len({p["number"] for p in rows}) == len(rows), "Duplicate proposal number")
        selected = [p for p in rows if p["number"] == number]
        _require(len(selected) == 1, "No unique proposal for canonical draft number")
        proposal = selected[0]
    else:
        proposal = container
    _require(_positive_int(proposal.get("number")) and proposal["number"] == number,
             "Proposal number differs from canonical draft")
    _require(proposal.get("decision") == "ACCEPT", "Sutrakar proposal must ACCEPT")
    _require(isinstance(proposal.get("journey_stage"), str)
             and proposal["journey_stage"] in JOURNEY,
             "Accepted Sutrakar proposal requires a known journey_stage")
    return proposal


def _eligible(result):
    """Validate saved final dispositions and canonical binding; never repair."""
    _require(isinstance(result, dict)
             and result.get("status") == "READY_FOR_AUTHOR_REVIEW", "Result is not ready")
    draft, assessment, review = (result.get(k) for k in ("draft", "assessment", "review"))
    _require(isinstance(draft, dict) and _text(draft.get("id"))
             and _positive_int(draft.get("number")) and _positive_int(draft.get("chapter")),
             "Draft needs canonical ID, logical number and chapter")
    _require(isinstance(assessment, dict) and assessment.get("status") == "PASS",
             "Assessment must PASS")
    _require(assessment.get("issues", []) == [], "PASS assessment contains unresolved issues")
    _require(isinstance(review, dict) and review.get("verdict") == "PASS"
             and review.get("outcome") == "READY", "Review must be PASS with outcome READY")
    for key in ("issues", "blocking_issues", "uncertainties"):
        _require(review.get(key, []) == [], "READY review contains unresolved findings")
    if "typed_review" in review:
        typed = review["typed_review"]
        _require(isinstance(typed, dict) and typed.get("outcome") == "READY"
                 and typed.get("blocking_issues") == [] and typed.get("uncertainties") == [],
                 "Typed review contradicts READY or is incomplete")
    draft_hash = canonical_hash(draft)
    _require(review.get("reviewed_draft_sha256") == draft_hash,
             "Reviewed canonical draft SHA256 mismatch")
    if "number" in result:
        _require(type(result["number"]) is int and result["number"] == draft["number"],
                 "Result number differs from canonical draft")
    return draft, _selected_proposal(result.get("proposal"), draft["number"]), draft_hash


def _content(entry):
    """Exclude only the two presentation metadata fields from preservation proof."""
    return {key: value for key, value in entry.items() if key not in {"number", "chapter"}}


def prepare_presentation(results, references, *, diagnostic_pilot=False, reference_display_overlay=None):
    """Pure mapping of explicit results to display copies plus provenance.

    Return entries/chapters/references/receipt. Reject any invalid selected result,
    duplicate canonical ID/number or missing citation. No input is mutated and
    no source, case, formula or prose is rewritten. The supplied list position
    is the explicit stable order; filenames and gapped logical numbers do not
    determine presentation order.
    """
    _require(isinstance(results, list) and bool(results), "Explicit nonempty result list required")
    registry = reference_registry(references)
    rows, ids, numbers = [], set(), set()
    for stable_order, result in enumerate(results, 1):
        draft, proposal, draft_hash = _eligible(result)
        _require(draft["id"] not in ids and draft["number"] not in numbers,
                 "Duplicate canonical draft ID or logical number")
        ids.add(draft["id"])
        numbers.add(draft["number"])
        refs = draft.get("references")
        _require(isinstance(refs, list) and bool(refs) and all(_text(r) for r in refs),
                 "Draft requires explicit reference IDs")
        _require(len(set(refs)) == len(refs) and all(r in registry for r in refs),
                 "Duplicate or missing canonical reference")
        proposal_refs = proposal.get("selected_source_ids", [])
        _require(isinstance(proposal_refs, list) and all(_text(r) and r in registry
                 for r in proposal_refs), "Proposal references missing from registry")
        rows.append((JOURNEY[proposal["journey_stage"]], stable_order, result, proposal, draft_hash))
    stages = {row[3]["journey_stage"] for row in rows}
    _require(diagnostic_pilot or {"opening", "closure"} <= stages,
             "Final book requires accepted opening and closure; use --diagnostic-pilot for partial QA")
    entries, numbering = [], []
    for display_number, (rank, stable_order, result, proposal, draft_hash) in enumerate(
            sorted(rows, key=lambda row: (row[0], row[1])), 1):
        original = result["draft"]
        display = deepcopy(original)
        display["number"], display["chapter"] = display_number, rank + 1
        _require(_content(original) == _content(display), "Protected draft content changed")
        entries.append(display)
        numbering.append({
            "id": original["id"], "canonical_number": original["number"],
            "canonical_chapter": original["chapter"], "stable_input_order": stable_order,
            "journey_stage": proposal["journey_stage"], "display_number": display_number,
            "presentation_chapter": rank + 1,
            "canonical_draft_sha256": draft_hash,
            "reviewed_draft_sha256": result["review"]["reviewed_draft_sha256"],
            "presentation_draft_sha256": canonical_hash(display),
            "unchanged_content_sha256": canonical_hash(_content(original)),
            "review_binding_verified_against": "canonical_draft_only",
            "presentation_copy_independently_reviewed": False,
            "changed_fields": [key for key in ("number", "chapter") if display[key] != original[key]],
            "result_canonical_sha256": canonical_hash(result),
            "proposal_sha256": canonical_hash(result["proposal"]),
            "selected_proposal_sha256": canonical_hash(proposal),
            "lineage": deepcopy({key: value for key, value in result.items() if key != "draft"}),
        })
    chapter_numbers = sorted({e["chapter"] for e in entries})
    chapters = [{"number": n, "title_mr": CHAPTER_TITLES[n]} for n in chapter_numbers]
    receipt = {
        "schema_version": 1,
        "mode": "DIAGNOSTIC_PILOT" if diagnostic_pilot else "FINAL_BOOK_PRESENTATION",
        "status": "PRESENTATION_PREPARED_NOT_EXPORTED",
        "ordering": "JOURNEY rank, then explicit result-list position (1-based)",
        "journey_ranks": dict(JOURNEY),
        "numbering_map": numbering,
        "presentation_entries_sha256": canonical_hash(entries),
        "canonical_references_sha256": canonical_hash(registry),
        "canonical_reference_record_hashes": {k: canonical_hash(v) for k, v in registry.items()},
        "chapters": deepcopy(chapters),
        "metadata_only_fields": ["number", "chapter"],
        "content_preservation": "All other JSON values and string contents unchanged; input file bytes untouched.",
        "review_scope": "Review hashes bind canonical drafts, not renumbered presentation copies.",
        "author_approval": "PENDING", "publication_approved": False,
        "visual_qa": "NOT_RUN", "new_generation": False,
    }
    presentation = {"entries": entries, "chapters": chapters, "references": registry, "receipt": receipt}
    if reference_display_overlay is not None:
        presentation["display_references"], receipt["reference_display"] = reference_display(
            registry, reference_display_overlay)
    return presentation


def _unique_object(pairs):
    """Refuse ambiguous duplicate JSON keys rather than silently discarding data."""
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"Nonfinite JSON value: {value}")


def _read_json(path):
    """Read one explicit input and retain its exact byte hash."""
    path = Path(path).resolve()
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                       parse_constant=_invalid_constant)
    return value, {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


def _asset(path, approved, expected):
    """Check both preflight identity and the renderer's unchanged template identity."""
    _require(isinstance(approved, dict) and approved.get("sha256") == expected
             and approved.get("expected_sha256", expected) == expected
             and approved.get("hash_matches") is True, "Preflight template identity mismatch")
    path = Path(path).resolve()
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    _require(actual == expected, "Template SHA256 differs from approved preflight")
    return {"path": str(path), "sha256": actual}


def export(result_paths, references, opening, closing, output, *,
           diagnostic_pilot=False, preflight=PREFLIGHT, reference_display=None):
    """Export explicit ready results and a NEW adjacent .qa.json receipt.

    All eligibility checks happen before the renderer. Existing outputs/receipts
    are never overwritten. A late receipt/write/QA failure may leave a newly
    rendered DOCX for diagnosis; it is never deleted or silently re-exported.
    This function does not invoke Word/PDF or claim fresh pixel preservation.
    """
    _require(isinstance(result_paths, (list, tuple)) and bool(result_paths),
             "Explicit result paths required")
    paths = [Path(p).resolve() for p in result_paths]
    _require(len(set(paths)) == len(paths), "Duplicate result path")
    output = Path(output).resolve()
    receipt_path = output.with_suffix(".qa.json")
    _require(output.suffix.lower() == ".docx", "Output must be .docx")
    for path in (output, receipt_path):
        if path.exists() or path.is_symlink():
            raise FileExistsError(path)
    if not output.parent.is_dir():
        raise FileNotFoundError(output.parent)
    results, inputs = [], []
    for path in paths:
        result, binding = _read_json(path)
        results.append(result)
        inputs.append(binding)
    registry, registry_binding = _read_json(references)
    overlay, overlay_binding = None, None
    if reference_display is not None:
        overlay, overlay_binding = _read_json(reference_display)
    presentation = prepare_presentation(results, registry, diagnostic_pilot=diagnostic_pilot,
                                        reference_display_overlay=overlay)
    approval, preflight_binding = _read_json(preflight)
    _require(isinstance(approval, dict)
             and approval.get("status") == "PASS_OFFLINE_EXPORT_PREFLIGHT_ONLY",
             "Approved export preflight required")
    assets = approval.get("assets", {})
    _require(isinstance(assets, dict), "Missing preflight assets")
    templates = {
        "opening": _asset(opening, assets.get("opening_v19"), research_book.OPENING_SHA256),
        "closing": _asset(closing, assets.get("closing_source"), research_book.CLOSING_SHA256),
    }
    snapshots = inputs + [registry_binding, preflight_binding] + list(templates.values())
    if overlay_binding is not None:
        snapshots.append(overlay_binding)
    before = canonical_hash(presentation)
    renderer_report = render_research_book(
        Path(templates["opening"]["path"]), Path(templates["closing"]["path"]),
        presentation["entries"], presentation["chapters"],
        presentation.get("display_references", presentation["references"]), output)
    _require(canonical_hash(presentation) == before, "Renderer mutated presentation inputs")
    for binding in snapshots:
        _require(hashlib.sha256(Path(binding["path"]).read_bytes()).hexdigest() == binding["sha256"],
                 f"Input changed during export: {binding['path']}")
    report = presentation["receipt"]
    report.update({
        "status": "EXPORTED_FOR_AUTHOR_REVIEW",
        "result_files_in_explicit_order": inputs,
        "reference_registry_file": registry_binding,
        "approved_preflight_file": preflight_binding,
        "templates": templates,
        "renderer": "src.doc_export.research_book.render_research_book",
        "renderer_report": renderer_report,
        "output": str(output),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "qa_receipt": str(receipt_path),
        "fresh_word_pdf_render": "NOT_RUN",
        "fresh_protected_page_pixel_comparison": "NOT_RUN",
    })
    if overlay_binding is not None:
        report["reference_display_file"] = overlay_binding
    for row in report["numbering_map"]:
        row["result_file"] = deepcopy(inputs[row["stable_input_order"] - 1])
    with receipt_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, allow_nan=False, indent=2)
        handle.write("\n")
    return report


def main(argv=None):
    """Parse explicit offline inputs; return a status code without hidden discovery."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, nargs="+", action="append", required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--reference-display", type=Path, help="Optional Marathi reference-label overlay JSON")
    parser.add_argument("--opening", type=Path, required=True)
    parser.add_argument("--closing", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, default=PREFLIGHT)
    parser.add_argument("--diagnostic-pilot", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = export([p for group in args.result for p in group], args.references,
                        args.opening, args.closing, args.output,
                        diagnostic_pilot=args.diagnostic_pilot, preflight=args.preflight,
                        reference_display=args.reference_display)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Export refused: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline structural acceptance for source-packet-based business entries.

PASS means the supplied structure, exact case provenance and literal duplicate
checks passed. It does not certify Sanskrit, Marathi quality, factual truth,
source interpretation, semantic originality or scholar/author approval. Packets
must be curated independently. This module performs no I/O or provider imports.
"""

import unicodedata
from urllib.parse import urlsplit

from src.orchestration.book_acceptance import sutra_shape_issues


CASE_FIELDS = ("case_id", "kind", "entity", "text_mr", "url", "source_title")
REFERENCE_FIELDS = ("id", "title", "author", "locator", "original_text",
                    "meaning_mr", "url", "tradition")
TEXT_FIELDS = ("id", "title_mr", "new_sutra", "grammar_mr", "translation_mr",
               "application_mr", "action_mr", "summary_mr")


def _nonempty(value: object) -> bool:
    """Return whether an untrusted field is a nonblank string; never coerce it."""
    return isinstance(value, str) and bool(value.strip())


def _web_url(value: object) -> bool:
    """Check HTTP(S) URL structure only, without fetching or verifying a source."""
    if not _nonempty(value) or any(char.isspace() for char in value):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname)
    except ValueError:
        return False


def _normalize_formula(value: str) -> str:
    """Normalize NFC and remove punctuation/whitespace for literal comparisons.

    Nasals, vowel marks, other letters and symbols remain distinct. This does
    not transliterate, equate spelling variants or detect semantic plagiarism.
    """
    return "".join(char for char in unicodedata.normalize("NFC", value)
                   if not char.isspace()
                   and not unicodedata.category(char).startswith("P"))


def _devanagari_word(token: str) -> bool:
    """Recognize one script-only word, allowing edge punctuation and joiners.

    Reject Latin/mixed-script tokens, numerals and standalone combining marks.
    This script test cannot distinguish Marathi from other Devanagari languages.
    """
    token = token.replace("\u200c", "").replace("\u200d", "")
    while token and unicodedata.category(token[0]).startswith("P"):
        token = token[1:]
    while token and unicodedata.category(token[-1]).startswith("P"):
        token = token[:-1]
    return (bool(token)
            and any(unicodedata.category(char).startswith("L") for char in token)
            and all(unicodedata.category(char)[0] in {"L", "M"}
                    and unicodedata.name(char, "").startswith("DEVANAGARI")
                    for char in token))


def _index_records(value: object, key: str, label: str,
                   issues: list[str]) -> dict[str, dict]:
    """Index packet records; append structural/duplicate-ID issues, without I/O."""
    result = {}
    if not isinstance(value, list) or not value:
        issues.append(f"{label} must be a nonempty list")
        return result
    for item in value:
        if not isinstance(item, dict) or not _nonempty(item.get(key)):
            issues.append(f"{label} record requires nonempty {key}")
            continue
        identifier = item[key]
        if identifier in result:
            issues.append(f"Duplicate {label} ID: {identifier}")
        result[identifier] = item
    return result


def assess_research_entry(entry: dict, source_packet: dict,
                          prior_formulas: list[str], forbidden_originals: list[str],
                          used_case_ids: set[str]) -> dict:
    """Assess one generated entry against its independently curated packet.

    Inputs: flat entry, canonical references and exactly two canonical cases,
    previous/generated and author-original formula lists, and globally used
    case IDs. Output: {status: PASS|NEEDS_REVISION, issues: list[str]}.
    Malformed inputs fail closed; inputs are never mutated. Inspect issue
    messages and the original packet to repair failures. PASS is structural
    acceptance only, never scholarly certification or permission to publish.
    """
    issues: list[str] = []
    if not isinstance(entry, dict) or not isinstance(source_packet, dict):
        return {"status": "NEEDS_REVISION",
                "issues": ["entry and source_packet must be dictionaries"]}

    for field in TEXT_FIELDS:
        if not _nonempty(entry.get(field)):
            issues.append(f"Missing or empty {field}")
    number = entry.get("number")
    if type(number) is not int or number < 1:
        issues.append("number must be a positive integer")
    chapter = entry.get("chapter")
    if not (_nonempty(chapter) or (type(chapter) is int and chapter > 0)):
        issues.append("chapter must be a nonempty label or positive integer")

    verse = entry.get("new_sutra")
    issues.extend(sutra_shape_issues(verse))
    if isinstance(verse, str):
        words = verse.strip().strip("।॥").strip().split()
        if not words or not all(_devanagari_word(word) for word in words):
            issues.append("New Sanskrit sutra must contain Devanagari word tokens")
    for label, formulas in (("prior_formulas", prior_formulas),
                            ("forbidden_originals", forbidden_originals)):
        if not isinstance(formulas, list) or any(not _nonempty(v) for v in formulas):
            issues.append(f"{label} must be a list of nonempty strings")
        elif isinstance(verse, str) and _normalize_formula(verse) in {
                _normalize_formula(v) for v in formulas}:
            issues.append(f"Normalized duplicate formula in {label}")

    exposition = entry.get("exposition")
    if (not isinstance(exposition, list) or not exposition
            or any(not _nonempty(p) for p in exposition)):
        issues.append("exposition must be a nonempty list of nonempty paragraphs")
    paragraphs = exposition if isinstance(exposition, list) else []
    count = sum(_devanagari_word(token) for paragraph in paragraphs
                if isinstance(paragraph, str) for token in paragraph.split())
    if count < 500:
        issues.append(f"exposition has {count} Devanagari word tokens; at least 500 required")
    for field in ("dos_mr", "donts_mr"):
        values = entry.get(field)
        if (not isinstance(values, list) or len(values) < 3
                or any(not _nonempty(value) for value in values)):
            issues.append(f"{field} requires at least three nonempty items")

    canonical_refs = _index_records(source_packet.get("references"), "id",
                                    "packet references", issues)
    references = entry.get("references")
    chosen = set()
    if not isinstance(references, list) or not references:
        issues.append("references must be a nonempty list of source IDs")
    else:
        for source_id in references:
            if not _nonempty(source_id):
                issues.append("references must contain nonempty source ID strings")
                continue
            if source_id in chosen:
                issues.append(f"Repeated reference ID: {source_id}")
            chosen.add(source_id)
            reference = canonical_refs.get(source_id)
            if reference is None:
                issues.append(f"Reference ID not in packet: {source_id}")
                continue
            for field in REFERENCE_FIELDS:
                if not _nonempty(reference.get(field)):
                    issues.append(f"Reference {source_id} requires {field}")
            if not _web_url(reference.get("url")):
                issues.append(f"Reference {source_id} requires an HTTP(S) source URL")

    comparisons = entry.get("comparative_mr")
    compared = set()
    if not isinstance(comparisons, list):
        issues.append("comparative_mr must be a list of per-reference comparisons")
    else:
        for comparison in comparisons:
            if not isinstance(comparison, dict) or not _nonempty(comparison.get("source_id")):
                issues.append("Comparison requires a nonempty source_id")
                continue
            source_id = comparison["source_id"]
            if source_id not in chosen:
                issues.append(f"Comparison refers to unchosen source: {source_id}")
            if source_id in compared:
                issues.append(f"Repeated comparison for source: {source_id}")
            compared.add(source_id)
            if not _nonempty(comparison.get("explanation_mr")):
                issues.append(f"Comparison {source_id} requires explanation_mr")
    for source_id in sorted(chosen - compared):
        issues.append(f"Missing comparison for reference: {source_id}")

    canonical_cases = _index_records(source_packet.get("examples"), "case_id",
                                     "packet examples", issues)
    kinds = []
    for case_id, case in canonical_cases.items():
        for field in CASE_FIELDS:
            if not _nonempty(case.get(field)):
                issues.append(f"Packet case {case_id} requires {field}")
        kinds.append(case.get("kind"))
        if not _web_url(case.get("url")):
            issues.append(f"Packet case {case_id} requires an HTTP(S) source URL")
    if len(kinds) != 2 or kinds.count("positive") != 1 or kinds.count("caution") != 1:
        issues.append("Packet must provide exactly one positive and one caution case")

    if (not isinstance(used_case_ids, set)
            or any(not _nonempty(case_id) for case_id in used_case_ids)):
        issues.append("used_case_ids must be a set of nonempty case ID strings")
        used_case_ids = set()
    examples = entry.get("examples")
    seen = set()
    if not isinstance(examples, list) or len(examples) != 2:
        issues.append("examples must contain exactly the two supplied cases")
    if isinstance(examples, list):
        for example in examples:
            if not isinstance(example, dict) or not _nonempty(example.get("case_id")):
                issues.append("Example requires a nonempty case_id")
                continue
            case_id = example["case_id"]
            if case_id in seen:
                issues.append(f"Repeated case ID within entry: {case_id}")
            seen.add(case_id)
            if case_id in used_case_ids:
                issues.append(f"Case ID already used in another entry: {case_id}")
            canonical = canonical_cases.get(case_id)
            if canonical is None:
                issues.append(f"Case ID not in packet: {case_id}")
            else:
                for field in CASE_FIELDS:
                    if field not in example or example[field] != canonical.get(field):
                        issues.append(f"Case {case_id} changed canonical field: {field}")
    if seen != set(canonical_cases):
        issues.append("Example case IDs must match exactly the provided packet case IDs")
    return {"status": "NEEDS_REVISION" if issues else "PASS", "issues": issues}

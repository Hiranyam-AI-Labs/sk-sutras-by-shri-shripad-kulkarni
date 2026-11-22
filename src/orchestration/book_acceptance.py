"""Deterministic minimum checks for unapproved Marathi book chapters."""

import re
import unicodedata
from typing import Any

SUTRA_MAX_CHARS = 32
SUTRA_MAX_WORDS = 4


def sutra_shape_issues(value: object) -> list[str]:
    """Check the verse's compact form before any downstream paid review.

    ``value`` is a draft string or a proposal object with a ``text`` field.
    Return exact shape failures; this cannot judge Sanskrit grammar or meaning.
    Inspect the complete verse when a proposal or chapter fails this gate.
    """
    if isinstance(value, dict):
        value = value.get("text")
    verse_text = value.strip().strip("।॥").strip() if isinstance(value, str) else ""
    issues = []
    if not 2 <= len(re.findall(r"[^\s।॥]+", verse_text)) <= SUTRA_MAX_WORDS:
        issues.append("New Sanskrit sutra must have two to four words")
    if len(verse_text) > SUTRA_MAX_CHARS or "," in verse_text or "，" in verse_text:
        issues.append("New Sanskrit sutra exceeds 32 characters or reads as a compound sentence")
    return issues


def marathi_words(value: str) -> int:
    """Count prose words in one generated Marathi field.

    ``value`` is the untrusted explanation text. Returns a whitespace word
    count, or zero for non-text input; it does not infer language or quality.
    Inspect the stored chapter field when a count is unexpectedly low.
    """
    return len(value.split()) if isinstance(value, str) else 0


def identity_aliases(value: str) -> set[str]:
    """Find literal and parenthesized person/business names for repeat checks.

    Input is one untrusted displayed identity. Returns normalized name forms;
    empty labels yield no aliases. This does not transliterate scripts, so an
    author must still review cross-script identities and corporate relations.
    """
    if not isinstance(value, str):
        return set()
    normalized = unicodedata.normalize("NFKC", value).casefold()
    parts = [normalized, *re.split(r"[(),;/|]", normalized)]
    aliases = set()
    for part in parts:
        part = re.sub(r"\b(?:inc|incorporated|corp|corporation|ltd|limited|llc|company)\b\.?,?", "", part).strip()
        letters = "".join(char for char in part if unicodedata.category(char)[0] in {"L", "M", "N"})
        if len(letters) > 2:
            aliases.add(letters)
    return aliases


def check_chapter(chapter: dict[str, Any], source: dict[str, Any],
                  prior_examples: set[str], prior_verses: set[str]) -> dict[str, Any]:
    """Check the reader chapter without asserting scholarly correctness.

    Inputs are a generated chapter, exact source texts and earlier identities.
    Returns issue strings and observed word count; malformed fields fail closed.
    Inspect issues and the independent review before author submission.
    """
    issues: list[str] = []
    verse = chapter.get("new_sutra", "")
    issues.extend(sutra_shape_issues(verse))
    if isinstance(verse, str) and verse.strip() in prior_verses:
        issues.append("New sutra repeats an earlier formulation")
    for key in ("narada_sutra", "shandilya_sutra"):
        item = chapter.get(key)
        if not isinstance(item, dict) or item.get("text") != source[key]["text"]:
            issues.append(f"Exact source text missing or changed: {key}")
        if not isinstance(item, dict) or not isinstance(item.get("brief_meaning_mr"), str) or not item["brief_meaning_mr"].strip():
            issues.append(f"Brief Marathi source explanation missing: {key}")
    for key in ("translation_mr", "padaccheda", "anvaya", "nirukta", "derivation_mr",
                "reflection_mr", "reader_action_mr"):
        if not isinstance(chapter.get(key), str) or not chapter[key].strip():
            issues.append(f"Missing {key}")
    count = marathi_words(chapter.get("explanation_mr"))
    if count < 500:
        issues.append(f"Marathi explanation has {count} words; at least 500 required")
    examples = chapter.get("examples")
    if not isinstance(examples, list) or len(examples) < 2:
        issues.append("At least two factual examples required")
    else:
        seen: set[str] = set()
        prior_aliases = set().union(*(identity_aliases(value) for value in prior_examples))
        kinds: set[str] = set()
        for example in examples:
            if not isinstance(example, dict) or not all(isinstance(example.get(k), str) and example[k].strip()
                                                        for k in ("person", "business", "description_mr", "source")):
                issues.append("Example identity, Marathi description or source missing")
                continue
            if example.get("kind") not in {"positive", "cautionary"}:
                issues.append("Example kind must be positive or cautionary")
            else:
                kinds.add(example["kind"])
            for key in ("person", "business"):
                forms = identity_aliases(example[key])
                if forms & (prior_aliases | seen):
                    issues.append(f"Repeated example identity: {example[key]}")
                seen.update(forms)
        if kinds != {"positive", "cautionary"}:
            issues.append("Both a positive and a cautionary business example are required")
    for key in ("dos_mr", "donts_mr"):
        values = chapter.get(key)
        if not isinstance(values, list) or len(values) < 3 or any(not isinstance(v, str) or not v.strip() for v in values):
            issues.append(f"At least three practical Marathi {key} required")
    return {"status": "READY_FOR_SCHOLAR_REVIEW" if not issues else "NEEDS_REVISION",
            "issues": issues, "explanation_words": count}

"""Verified passage packets from registered local manuscript and IKS sources."""

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List


def _terms(value: str) -> set[str]:
    """Return Unicode letter/mark tokens including Devanagari vowel signs.

    ``value`` is untrusted source or query text; punctuation separates terms.
    Empty or short fragments are ignored. Inspect the original paragraph if a
    Sanskrit quotation has unexpectedly poor retrieval rank.
    """
    words, current = [], []
    for char in value.casefold():
        if unicodedata.category(char)[0] in {"L", "M", "N"}:
            current.append(char)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    return {word for word in words if len(word) > 2}


def retrieve_passages(sources: Dict[str, Path], query: str, limit: int = 2) -> List[dict]:
    """Find relevant passages in each registered source without invented quotations.

    ``sources`` maps stable IDs to local text paths; ``query`` is the theme and
    ``limit`` caps excerpts per source. Returns identity, file hash, paragraph
    location and verbatim text. Missing files, empty retrieval, and invalid limits
    raise; inspect source IDs and query terms to debug a blocked handoff.
    """
    if not query.strip() or limit < 1 or not sources:
        raise ValueError("Registered sources, nonblank query, and positive limit required")
    terms = _terms(query)
    result = []
    for source_id, path in sources.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        raw = path.read_bytes()
        if b"Command output:" in raw or b"Traceback (most recent call last)" in raw:
            raise ValueError(f"Registered source contains tool-output contamination: {source_id}")
        content = raw.decode("utf-8")
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        ranked = []
        for number, paragraph in enumerate(paragraphs, 1):
            if (len(paragraph) < 15 or paragraph.lower().startswith(("http://", "https://")) or
                    "Command output:" in paragraph or "Traceback (most recent call last)" in paragraph):
                continue
            overlap = terms & _terms(paragraph)
            score = sum(3 if any("\u0900" <= char <= "\u097f" for char in word) else 1
                        for word in overlap)
            if score >= 2:
                ranked.append((score, number, paragraph))
        for _, number, passage in sorted(ranked, key=lambda item: (-item[0], item[1]))[:limit]:
            result.append({"source_id": source_id, "source_version": hashlib.sha256(raw).hexdigest(),
                           "location": f"paragraph:{number}", "text": passage})
    if not result:
        raise ValueError("No relevant passage found in registered sources")
    return result


def retrieve_iks_vector_passages(client: object, corpus_path: Path, query: str,
                                 limit: int = 3) -> List[dict]:
    """Retrieve IKS IDs semantically, then verify text against the local corpus.

    ``client`` exposes the existing iks_canonical_library Chroma collection.
    Returns versioned, located source passages; missing index, unknown IDs, or
    malformed records raise. Reingest the corpus before retrying an index gap.
    """
    if not query.strip() or limit < 1 or not corpus_path.is_file():
        raise ValueError("IKS corpus, query and positive result limit required")
    raw = corpus_path.read_bytes()
    records = json.loads(raw.decode("utf-8"))
    by_id = {record["id"]: record for record in records}
    collection = client.get_collection("iks_canonical_library")
    if collection.count() < 1:
        raise ValueError("IKS vector collection is empty")
    result = collection.query(query_texts=[query], n_results=limit)
    ids = (result or {}).get("ids", [[]])[0]
    if not ids:
        raise ValueError("IKS vector retrieval returned no passages")
    passages = []
    for record_id in ids:
        record = by_id.get(record_id)
        if not record or not all(record.get(key) for key in
                                 ("tradition", "section", "verse_no", "sanskrit", "english_meaning")):
            raise ValueError(f"IKS vector ID absent or incomplete in source: {record_id}")
        passages.append({"source_id": f"IKS:{record_id}",
                         "source_version": hashlib.sha256(raw).hexdigest(),
                         "location": f"{record['tradition']}:{record['section']}:{record['verse_no']}",
                         "text": f"{record['sanskrit']} — {record['english_meaning']}"})
    return passages


def require_handoff(packet: Iterable[dict], bridge: str, composition_prompt: str,
                    audit_prompt: str) -> None:
    """Verify both author and verifier received exact passage IDs and bridge.

    Inputs are retrieved packet, Agent 3 bridge, and final prompts. Returns None;
    ValueError blocks omitted evidence. Inspect source IDs and prompts without
    credentials when debugging a handoff failure.
    """
    entries = list(packet)
    if not entries or not bridge.strip():
        raise ValueError("Passages and independent research bridge required")
    for prompt in (composition_prompt, audit_prompt):
        if bridge not in prompt or any(item["source_id"] not in prompt or
                                   item["text"] not in prompt for item in entries):
            raise ValueError("Source evidence omitted from author or verifier handoff")

"""Verified passage packets from registered local manuscript and IKS sources."""

import hashlib
import re
from pathlib import Path
from typing import Dict, Iterable, List


def retrieve_passages(sources: Dict[str, Path], query: str, limit: int = 2) -> List[dict]:
    """Find relevant passages in each registered source without invented quotations.

    ``sources`` maps stable IDs to local text paths; ``query`` is the theme and
    ``limit`` caps excerpts per source. Returns identity, file hash, paragraph
    location and verbatim text. Missing files, empty retrieval, and invalid limits
    raise; inspect source IDs and query terms to debug a blocked handoff.
    """
    if not query.strip() or limit < 1 or not sources:
        raise ValueError("Registered sources, nonblank query, and positive limit required")
    terms = {word.casefold() for word in re.findall(r"\w+", query) if len(word) > 2}
    result = []
    for source_id, path in sources.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        raw = path.read_bytes()
        content = raw.decode("utf-8")
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        ranked = []
        for number, paragraph in enumerate(paragraphs, 1):
            score = len(terms & {w.casefold() for w in re.findall(r"\w+", paragraph)})
            if score:
                ranked.append((score, number, paragraph))
        for _, number, passage in sorted(ranked, key=lambda item: (-item[0], item[1]))[:limit]:
            result.append({"source_id": source_id, "source_version": hashlib.sha256(raw).hexdigest(),
                           "location": f"paragraph:{number}", "text": passage})
    if not result:
        raise ValueError("No relevant passage found in registered sources")
    return result


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

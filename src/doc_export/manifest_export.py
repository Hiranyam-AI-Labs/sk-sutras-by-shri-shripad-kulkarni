"""Publication input validation from a frozen human-approved manifest.

Renderers may consume this validated payload; they must not invent missing text.
"""

import json
from pathlib import Path
from typing import Any, Dict

from src.orchestration.review_store import fingerprint


SECTION_KEYS = ("sources", "derivation", "sutra_meaning", "commentary",
                "cases_yoga", "dos_donts", "reflection")


def validate_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Verify exact content hashes, fifteen gates and all seven substantive sections.

    ``manifest`` is a frozen ReviewStore result, not arbitrary renderer input.
    Returns the validated object; missing/blank sections, mismatched fingerprints
    or non-PASS gates raise ValueError. Inspect unit ID and stored version to debug.
    """
    units = manifest.get("units")
    if not isinstance(units, list) or not units:
        raise ValueError("Approved manifest requires units")
    for entry in units:
        content = entry.get("content")
        if not isinstance(content, dict) or fingerprint(content) != entry.get("content_sha256"):
            raise ValueError("Manifest content fingerprint mismatch")
        sections = content.get("sections")
        if not isinstance(sections, dict) or any(
            not isinstance(sections.get(key), str) or not sections[key].strip()
            for key in SECTION_KEYS
        ):
            raise ValueError(f"Seven substantive sections missing: {entry.get('unit_id')}")
        gates = entry.get("gates")
        if not isinstance(gates, dict) or len(gates) != 15 or any(v != "PASS" for v in gates.values()):
            raise ValueError("All fifteen versioned gates required")
    return manifest


def export_manifest_json(manifest: Dict[str, Any], destination: Path) -> None:
    """Write only a validated frozen manifest to the explicit destination.

    ``destination`` is a caller-selected publication path. Returns None; failed
    validation or write errors propagate. Inspect the destination permissions and
    manifest hash to debug; no filler text or historical repair is performed.
    """
    validated = validate_manifest(manifest)
    destination.write_text(json.dumps(validated, ensure_ascii=False, indent=2), encoding="utf-8")

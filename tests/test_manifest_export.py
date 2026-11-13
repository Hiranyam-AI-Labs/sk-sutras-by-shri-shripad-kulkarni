"""Publication never fills absent manuscript sections or accepts stale hashes."""

import importlib.util
from pathlib import Path

import pytest

from src.agents.acceptance_policy import GATE_NAMES
from src.orchestration.review_store import fingerprint

module_path = Path(__file__).resolve().parents[1] / "src" / "doc_export" / "manifest_export.py"
spec = importlib.util.spec_from_file_location("manifest_export_standalone", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_missing_section_or_stale_content_blocks_export(tmp_path):
    """A valid gate score never supplies missing substantive text."""
    content = {"sections": {key: "verified text" for key in module.SECTION_KEYS}}
    entry = {"unit_id": "one", "content": content, "content_sha256": fingerprint(content),
             "gates": {key: "PASS" for key in GATE_NAMES}}
    manifest = {"manifest_id": "book", "units": [entry]}
    destination = tmp_path / "book.json"
    module.export_manifest_json(manifest, destination)
    assert destination.exists()
    content["sections"]["cases_yoga"] = ""
    with pytest.raises(ValueError):
        module.export_manifest_json(manifest, tmp_path / "invalid.json")
    assert not (tmp_path / "invalid.json").exists()

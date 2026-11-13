"""Source passage identity and prompt handoff failure boundaries."""

import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / "src" / "orchestration" / "source_evidence.py"
spec = importlib.util.spec_from_file_location("source_evidence_standalone", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_real_passage_location_and_handoff(tmp_path):
    """Source text, file version and paragraph location survive author and audit handoff."""
    source = tmp_path / "doc.txt"
    source.write_text("Ethical enterprise serves customers.\n\nUnrelated paragraph.", encoding="utf-8")
    packet = module.retrieve_passages({"DOC-01": source}, "ethical customers")
    assert packet[0]["location"] == "paragraph:1"
    assert packet[0]["text"] == "Ethical enterprise serves customers."
    evidence = f"Bridge DOC-01 {packet[0]['text']}"
    module.require_handoff(packet, "Bridge", evidence, evidence)
    with pytest.raises(ValueError):
        module.require_handoff(packet, "Bridge", evidence, "Audit without source")


def test_empty_retrieval_blocks(tmp_path):
    """No relevant passage produces an error instead of a canned quotation."""
    source = tmp_path / "doc.txt"
    source.write_text("Completely unrelated.", encoding="utf-8")
    with pytest.raises(ValueError):
        module.retrieve_passages({"DOC-01": source}, "governance")

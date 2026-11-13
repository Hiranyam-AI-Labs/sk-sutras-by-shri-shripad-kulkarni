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


def test_devanagari_words_rank_above_generic_links(tmp_path):
    """Combining marks remain in Sanskrit tokens and URL hits are excluded."""
    source = tmp_path / "doc.txt"
    source.write_text("https://example.test/bhakti-inquiry\n\n"
                      "अथातो भक्तिं व्याख्यास्यामः ॥ Source meaning.\n\n"
                      "The source is here.", encoding="utf-8")
    packet = module.retrieve_passages({"DOC-02": source},
                                      "अथातो भक्तिं व्याख्यास्यामः inquiry")
    assert packet[0]["location"] == "paragraph:2"
    assert all(not item["text"].startswith("https://") for item in packet)


def test_tool_output_contamination_blocks_registered_source(tmp_path):
    """A transcript fragment cannot become a cited manuscript passage."""
    source = tmp_path / "doc.txt"
    source.write_text("Ethical source paragraph.\n\nCommand output: fabricated result",
                      encoding="utf-8")
    with pytest.raises(ValueError, match="tool-output contamination"):
        module.retrieve_passages({"DOC-01": source}, "ethical source")

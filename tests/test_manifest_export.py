"""Publication never fills absent manuscript sections or accepts stale hashes."""

import importlib.util
from pathlib import Path

import pytest

from src.agents.acceptance_policy import GATE_NAMES
from src.agents.acceptance_policy import POLICY_VERSION
from src.database.example_registry import ExampleRegistry
from src.orchestration.review_store import ReviewStore, fingerprint

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


def test_frozen_manifest_renders_word_and_pdf_without_filler(tmp_path):
    """Only a stored author-approved edition with committed examples can render."""
    from docx import Document
    from pypdf import PdfReader

    font = Path("C:/Windows/Fonts/Nirmala.ttc")
    if not font.is_file():
        pytest.skip("Local Devanagari font unavailable")
    path = tmp_path / "edition.db"
    store, registry = ReviewStore(path), ExampleRegistry(path)
    registry.register("Founder One", "PERSON", "synthetic source")
    content = {"sections": {key: f"Synthetic {key} evidence." for key in module.SECTION_KEYS},
               "named_examples": [{"name": "Founder One", "polarity": "POSITIVE", "location": "case"}]}
    report = {"policy_version": POLICY_VERSION,
              "gates": {key: "PASS" for key in GATE_NAMES}}
    version = store.save_draft("one", content, report)
    store.mark_ai_validated("one", version)
    digest = fingerprint(content)
    registry.reserve("one", content["named_examples"], digest)
    store.approve("one", version, "SCHOLAR", "Synthetic Scholar", digest)
    store.approve("one", version, "AUTHOR", "Synthetic Author", digest, registry)
    store.freeze_manifest("edition-one", [("one", version)], registry)
    docx_path, pdf_path = tmp_path / "book.docx", tmp_path / "book.pdf"
    module.export_approved_book(store, registry, "edition-one", docx_path, pdf_path, font)
    doc_text = "\n".join(p.text for p in Document(docx_path).paragraphs)
    pdf_text = "\n".join(page.extract_text() for page in PdfReader(pdf_path).pages)
    assert "Synthetic sources evidence." in doc_text
    assert "Synthetic reflection evidence." in pdf_text
    assert "जमशेदजी" not in doc_text
    with pytest.raises(FileExistsError):
        module.export_approved_book(store, registry, "edition-one", docx_path, pdf_path, font)
    store.save_draft("one", {**content, "revision": "new"}, report)
    with pytest.raises(ValueError, match="stale"):
        module.export_approved_book(store, registry, "edition-one", tmp_path / "new.docx",
                                    tmp_path / "new.pdf", font)

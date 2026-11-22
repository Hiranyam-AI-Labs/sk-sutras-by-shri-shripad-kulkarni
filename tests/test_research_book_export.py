"""Offline contract and package-preservation tests; outputs stay in pytest tmp_path."""

from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
import pytest

from src.doc_export import research_book as book


def _package(path, closing=False):
    """Write a synthetic template to path; return None; ZIP/XML errors propagate.

    closing selects source-default font fixtures rather than the V19 style slots.
    """
    root = etree.Element(book._w("document"), nsmap=book.NS)
    body = etree.SubElement(root, book._w("body"))
    for index in range(110):
        p = etree.SubElement(body, book._w("p"))
        p.set("{" + book.W14 + "}paraId", f"{index + 1:08X}")
        pp = etree.SubElement(p, book._w("pPr"))
        etree.SubElement(pp, book._w("jc")).set(book._w("val"), "left")
        for part in range(2):
            run = etree.SubElement(p, book._w("r"))
            rp = etree.SubElement(run, book._w("rPr"))
            etree.SubElement(rp, book._w("color")).set(book._w("val"), "1E1E1E" if part else "990000")
            etree.SubElement(run, book._w("t")).text = f"{'closing' if closing else 'opening'} {index} {part}"
    section = etree.SubElement(body, book._w("sectPr"))
    margins = etree.SubElement(section, book._w("pgMar"))
    for name in ("top", "bottom", "left", "right"):
        margins.set(book._w(name), "1440")
    styles = etree.Element(book._w("styles"), nsmap={"w": book.W})
    defaults = etree.SubElement(styles, book._w("docDefaults"))
    pr = etree.SubElement(etree.SubElement(defaults, book._w("pPrDefault")), book._w("pPr"))
    etree.SubElement(pr, book._w("spacing")).set(book._w("after"), "120")
    rp = etree.SubElement(etree.SubElement(defaults, book._w("rPrDefault")), book._w("rPr"))
    fonts = etree.SubElement(rp, book._w("rFonts"))
    fonts.set(book._w("ascii"), "Closing fixture font" if closing else "Cambria")
    etree.SubElement(rp, book._w("sz")).set(book._w("val"), "24")
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", etree.tostring(root))
        archive.writestr("word/styles.xml", etree.tostring(styles))
        archive.writestr("word/_rels/document.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr("word/media/preserved.bin", b"preserve every byte")
        archive.writestr("word/header1.xml", b"unchanged header fixture")


@pytest.fixture
def templates(tmp_path, monkeypatch):
    """Provide hash-bound synthetic template paths; pytest restores hashes; I/O errors propagate."""
    opening, closing = tmp_path / "opening.docx", tmp_path / "closing.docx"
    _package(opening)
    _package(closing, closing=True)
    monkeypatch.setattr(book, "OPENING_SHA256", hashlib.sha256(opening.read_bytes()).hexdigest())
    monkeypatch.setattr(book, "CLOSING_SHA256", hashlib.sha256(closing.read_bytes()).hexdigest())
    return opening, closing


@pytest.fixture
def content():
    """Return explicit nonpublication entry/reference fixtures; no external data or failures."""
    entry = {
        "id": "fixture-1", "number": 1, "chapter": 7, "title_mr": "चाचणी नोंद",
        "new_sutra": "अथातो उद्यमजिज्ञासा", "grammar_mr": "पदच्छेद आणि अन्वय चाचणी मजकूर",
        "translation_mr": "चाचणी अर्थ", "exposition": ["चाचणी मराठी शब्द " * 170],
        "references": ["ref-test"],
        "comparative_mr": [{"source_id": "ref-test", "explanation_mr": "तुलनात्मक चाचणी विवेचन"}],
        "examples": [
            {"case_id": "case-positive", "kind": "positive", "entity": "Fixture entity A",
             "text_mr": "अपरिवर्तनीय चाचणी दाखला अ", "url": "https://example.org/a", "source_title": "Fixture source A"},
            {"case_id": "case-caution", "kind": "caution", "entity": "Fixture entity B",
             "text_mr": "अपरिवर्तनीय चाचणी दाखला ब", "url": "https://example.org/b", "source_title": "Fixture source B"}],
        "dos_mr": ["कृती एक", "कृती दोन", "कृती तीन"],
        "donts_mr": ["टाळा एक", "टाळा दोन", "टाळा तीन"],
        "application_mr": "व्यवहार चाचणी", "action_mr": "कृती चाचणी", "summary_mr": "सारांश चाचणी",
    }
    references = {"ref-test": {"id": "ref-test", "title": "Fixture philosophy title",
                  "author": "Fixture author", "locator": "section 3", "original_text": "Exact original passage.",
                  "meaning_mr": "मूळ अर्थ चाचणी", "url": "https://example.org/philosophy", "tradition": "चाचणी परंपरा"}}
    return [entry], [{"number": 7, "title_mr": "सातवा अध्याय"}], references


def _parts(path):
    """Read a DOCX path into package bytes; return mapping; ZIP/I/O errors propagate."""
    with ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_preservation_centering_numbering_and_evidence_links(templates, content, tmp_path):
    """Render fixture inputs; assert package/text/link invariants; pytest reports mismatches."""
    entries, chapters, references = content
    before = deepcopy(content)
    original = _parts(templates[0])
    report = book.render_research_book(*templates, entries, chapters, references, tmp_path / "test.docx")
    assert content == before
    parts = _parts(tmp_path / "test.docx")
    body = etree.fromstring(parts["word/document.xml"]).find(book._w("body"))
    old_body = etree.fromstring(original["word/document.xml"]).find(book._w("body"))
    for old, new in zip(old_body.findall(book._w("p"))[:85], body.findall(book._w("p"))[:85]):
        assert etree.tostring(old, method="c14n", exclusive=True) == etree.tostring(new, method="c14n", exclusive=True)
    changed = {"word/document.xml", "word/styles.xml", "word/_rels/document.xml.rels", "[Content_Types].xml"}
    assert all(parts[name] == data for name, data in original.items() if name not in changed)
    paragraphs = body.findall(book._w("p"))
    texts = ["".join(p.xpath(".//w:t/text()", namespaces=book.NS)) for p in paragraphs]
    assert "अध्याय ७ : सातवा अध्याय" in texts
    assert "उद्यम सूत्र १ : चाचणी नोंद" in texts
    count_sentence = "या परीक्षणप्रतीत एकूण १ उद्यमसूत्रे आहेत."
    assert texts.count(count_sentence) == 1 and count_sentence in texts[85:]
    assert count_sentence not in texts[:85]
    formulas = [p for p in paragraphs if "".join(p.xpath(".//w:t/text()", namespaces=book.NS)).startswith("॥ ")]
    assert len(formulas) == 1
    assert formulas[0].find("./w:pPr/w:jc", book.NS).get(book._w("val")) == "center"
    assert formulas[0].find("./w:r/w:rPr/w:color", book.NS).get(book._w("val")) == "990000"
    assert all(font.get(book._w("cs")) == "Nirmala UI" for font in formulas[0].xpath(".//w:rFonts", namespaces=book.NS))
    anchors = set(body.xpath(".//w:hyperlink/@w:anchor", namespaces=book.NS))
    bookmarks = set(body.xpath(".//w:bookmarkStart/@w:name", namespaces=book.NS))
    assert anchors <= bookmarks
    assert {"ResearchRef_1", "ResearchRef_2", "ResearchRef_3"} <= anchors
    rels = etree.fromstring(parts["word/_rels/document.xml.rels"])
    targets = {r.get("Target") for r in rels if r.get("TargetMode") == "External"}
    assert targets == {"https://example.org/philosophy", "https://example.org/a", "https://example.org/b"}
    assert any("Fixture author — Fixture philosophy title — section 3" in text for text in texts)
    assert "Exact original passage." not in texts
    assert any("मूळ अर्थ चाचणी" in text for text in texts)
    for case in entries[0]["examples"]:
        assert any(text.startswith(case["text_mr"]) for text in texts)
    source_closing = etree.fromstring(_parts(templates[1])["word/document.xml"]).find(book._w("body")).findall(book._w("p"))[39:45]
    for old, new in zip(source_closing, list(body)[-7:-1]):
        assert old.xpath(".//w:t/text()", namespaces=book.NS) == new.xpath(".//w:t/text()", namespaces=book.NS)
        assert new.find("./w:pPr/w:pStyle", book.NS).get(book._w("val")) == "ClosingSourceNormal"
        assert new.find("./w:r/w:rPr/w:rFonts", book.NS).get(book._w("ascii")) == "Closing fixture font"
    assert body[-1].find(book._w("pgMar")).get(book._w("top")) == "1400"
    assert body[-1].find(book._w("type")).get(book._w("val")) == "nextPage"
    ids = body.xpath(".//@w14:paraId", namespaces={"w14": book.W14})
    assert len(ids) == len(set(ids))
    assert report["render_status"] == "NOT_RUN"
    assert report["case_entities"] == 2
    assert report["word_counts"]["fixture-1"]["devanagari_tokens"] == 510


def test_catalog_is_separate_and_not_numbered_as_evidence(templates, content, tmp_path):
    """Render an uncited catalog record; assert separation; pytest reports missing labels/links."""
    catalog = [{"id": "future", "title": "Proposed fixture book", "url": "https://example.org/future"}]
    report = book.render_research_book(*templates, *content, tmp_path / "catalog.docx", source_catalog=catalog)
    root = etree.fromstring(_parts(tmp_path / "catalog.docx")["word/document.xml"])
    text = " ".join(root.xpath(".//w:t/text()", namespaces=book.NS))
    assert "पुढील अभ्यासासाठी संदर्भग्रंथ" in text and "Proposed fixture book" in text
    assert "Proposed research" not in text
    assert text.count("या परीक्षणप्रतीत एकूण १ उद्यमसूत्रे आहेत.") == 1
    assert "या परीक्षणप्रतीत एकूण २ उद्यमसूत्रे आहेत." not in text
    assert report["cited_references"] == ["ref-test"]
    assert report["proposed_research_count"] == 1
    assert len(root.xpath('.//w:bookmarkStart[starts-with(@w:name,"ResearchRef_")]', namespaces=book.NS)) == 3
    assert "नारदभक्तिसूत्रांचा संदर्भसहचर" not in text


def test_sanskrit_original_appears_only_in_entry_not_bibliography(templates, content, tmp_path):
    """Render a canonical Sanskrit fixture; require one occurrence, with Marathi meaning retained."""
    entries, chapters, references = content
    references["ref-test"]["original_text"] = "अथातो भक्तिजिज्ञासा।"
    references["ref-test"]["tradition"] = "Indian Sanskrit"
    book.render_research_book(*templates, entries, chapters, references, tmp_path / "sanskrit.docx")
    root = etree.fromstring(_parts(tmp_path / "sanskrit.docx")["word/document.xml"])
    text = " ".join(root.xpath(".//w:t/text()", namespaces=book.NS))
    assert text.count("अथातो भक्तिजिज्ञासा।") == 1
    assert "अथातो भक्तिजिज्ञासा।" not in text.split("संदर्भसूची", 1)[1]


@pytest.mark.parametrize("tradition,label", [("Indian", "भारतीय"), ("Western", "पाश्चात्त्य"), ("Other", "अन्य")])
def test_tradition_labels_are_marathi_without_changing_canonical_values(templates, content, tmp_path, tradition, label):
    """Render each supported tradition; require Marathi entry/bibliography labels and unchanged evidence."""
    entries, chapters, references = content
    references["ref-test"]["tradition"] = tradition
    before = deepcopy(references)
    book.render_research_book(*templates, entries, chapters, references, tmp_path / "tradition.docx")
    root = etree.fromstring(_parts(tmp_path / "tradition.docx")["word/document.xml"])
    text = "\n".join(root.xpath(".//w:t/text()", namespaces=book.NS))
    assert text.count(label) == 2 and tradition not in text
    assert references == before


def test_marathi_reference_labels_preserve_canonical_evidence_and_nonbreaking_citations(templates, content, tmp_path):
    """Render display overrides; assert exact canonical inputs survive and citations cannot split at spaces."""
    entries, chapters, references = content
    ref = references["ref-test"]
    ref["locator"] = "Chapter II; paragraph beginning 'English source incipit'"
    ref.update(title_mr="स्वातंत्र्याविषयी", author_mr="जॉन स्टुअर्ट मिल",
               locator_mr="प्रकरण २ — विचार आणि चर्चेचे स्वातंत्र्य")
    before = deepcopy(content)
    report = book.render_research_book(*templates, entries, chapters, references, tmp_path / "display-labels.docx")
    assert content == before
    root = etree.fromstring(_parts(tmp_path / "display-labels.docx")["word/document.xml"])
    text = "\n".join(root.xpath(".//w:t/text()", namespaces=book.NS))
    assert ref["title"] not in text and ref["author"] not in text and ref["locator"] not in text
    assert "English source incipit" not in text and ref["original_text"] not in text
    assert text.count(ref["title_mr"]) == 2
    assert text.count(ref["locator_mr"]) == 2
    assert text.count(ref["author_mr"]) == 3  # Entry attribution, comparison and bibliography.
    assert ref["meaning_mr"] in text
    assert report["cited_references"] == [ref["id"]]
    links = root.xpath('.//w:hyperlink[starts-with(@w:anchor,"ResearchRef_")]', namespaces=book.NS)
    assert len(links) == 4
    for link in links:
        label = "".join(link.xpath('.//w:t/text()', namespaces=book.NS))
        assert label.startswith("\u00a0[संदर्भ\u00a0") and label.endswith("]")
        assert " " not in label
    relationships = etree.fromstring(_parts(tmp_path / "display-labels.docx")["word/_rels/document.xml.rels"])
    assert ref["url"] in {item.get("Target") for item in relationships}


@pytest.mark.parametrize("field", ["title", "author", "locator", "tradition"])
def test_partial_reference_label_overlay_retains_other_canonical_labels(templates, content, tmp_path, field):
    """Override just one label; require canonical fallback for the others without input mutation."""
    entries, chapters, references = content
    ref = references["ref-test"]
    ref[field + "_mr"] = "मराठी प्रदर्शन चाचणी"
    before = deepcopy(references)
    book.render_research_book(*templates, entries, chapters, references, tmp_path / "partial-label.docx")
    root = etree.fromstring(_parts(tmp_path / "partial-label.docx")["word/document.xml"])
    text = "\n".join(root.xpath(".//w:t/text()", namespaces=book.NS))
    assert "मराठी प्रदर्शन चाचणी" in text and ref[field] not in text
    assert all(ref[other] in text for other in ("title", "author", "locator") if other != field)
    assert references == before


@pytest.mark.parametrize("field", ["title_mr", "author_mr", "locator_mr", "tradition_mr"])
def test_empty_supplied_display_label_is_rejected_before_output(templates, content, tmp_path, field):
    """Supply a blank optional label; expect explicit validation failure rather than hidden fallback."""
    content[2]["ref-test"][field] = " "
    with pytest.raises(ValueError, match=field):
        book.render_research_book(*templates, *content, tmp_path / "bad-display-label.docx")
    assert not (tmp_path / "bad-display-label.docx").exists()


@pytest.mark.parametrize("reference_id", ["CMP012", "CMP013", "CMP014"])
def test_named_modern_references_cannot_repeat_across_entries(templates, content, tmp_path, reference_id):
    """Reuse a restricted source in two entries; expect prewrite rejection without evidence mutation."""
    entries, chapters, references = content
    ref = references.pop("ref-test")
    ref["id"] = reference_id
    references[reference_id] = ref
    entries[0]["references"] = [reference_id]
    entries[0]["comparative_mr"][0]["source_id"] = reference_id
    second = deepcopy(entries[0])
    second.update(id="second", number=2, new_sutra="चाचणी दुसरे सूत्र")
    for case in second["examples"]:
        case["case_id"] += "-second"
        case["entity"] += " second"
    entries.append(second)
    with pytest.raises(ValueError, match="limited to one entry"):
        book.render_research_book(*templates, entries, chapters, references, tmp_path / "repeat.docx")
    assert not (tmp_path / "repeat.docx").exists()


@pytest.mark.parametrize("defect", ["short", "english", "reference", "comparison", "case", "kind", "malformed_kind", "url", "grammar", "number", "chapter", "guidance", "duplicate", "catalog", "catalog_type"])
def test_invalid_contract_never_creates_output(templates, content, tmp_path, defect):
    """Corrupt one supplied invariant; expect ValueError and no output, leaving inputs local."""
    entries, chapters, references = content
    entry = entries[0]
    catalog = None
    if defect == "short":
        entry["exposition"] = ["मराठी " * 499]
    elif defect == "english":
        entry["exposition"] = ["English " * 600]
    elif defect == "reference":
        references["ref-test"]["id"] = "different"
    elif defect == "comparison":
        entry["comparative_mr"][0]["source_id"] = "unknown"
    elif defect == "case":
        entry["examples"][1]["entity"] = "FIXTURE ENTITY A"
    elif defect == "kind":
        entry["examples"][1]["kind"] = "positive"
    elif defect == "malformed_kind":
        entry["examples"][1]["kind"] = []
    elif defect == "url":
        entry["examples"][0]["url"] = "file:///private/source"
    elif defect == "grammar":
        entry["grammar_mr"] = " "
    elif defect == "number":
        entry["number"] = True
    elif defect == "chapter":
        entry["chapter"] = 99
    elif defect == "guidance":
        entry["dos_mr"] = ["एक"]
    elif defect == "duplicate":
        entries.append(deepcopy(entry))
    elif defect == "catalog":
        catalog = [{"id": "ref-test", "title": "Already cited"}]
    elif defect == "catalog_type":
        catalog = {}
    with pytest.raises(ValueError):
        book.render_research_book(*templates, entries, chapters, references, tmp_path / "invalid.docx", source_catalog=catalog)
    assert not (tmp_path / "invalid.docx").exists()


def test_hash_binding_and_existing_output_are_fail_closed(templates, content, tmp_path):
    """Reject modified template and occupied output; assert source/output bytes remain intact."""
    existing = tmp_path / "existing.docx"
    existing.write_bytes(b"do not overwrite")
    with pytest.raises(FileExistsError):
        book.render_research_book(*templates, *content, existing)
    assert existing.read_bytes() == b"do not overwrite"
    templates[0].write_bytes(templates[0].read_bytes() + b"changed")
    with pytest.raises(ValueError, match="SHA256"):
        book.render_research_book(*templates, *content, tmp_path / "wrong-template.docx")
    assert not (tmp_path / "wrong-template.docx").exists()


def test_more_than_one_hundred_entries_and_independent_chapter_numbers(templates, content, tmp_path):
    """Render 101 synthetic entries in two chapters; assert no upper cap, cases and numbering."""
    entries, _, references = content
    prototype = entries[0]
    entries = []
    for number in range(1, 102):
        entry = deepcopy(prototype)
        entry.update(id=f"fixture-{number}", number=number, chapter=7 if number <= 50 else 12,
                     new_sutra=f"चाचणी सूत्र {number}")
        for case in entry["examples"]:
            case["case_id"] += str(number)
            case["entity"] += str(number)
        entries.append(entry)
    chapters = [{"chapter": 7, "title": "अध्याय सात"}, {"chapter": 12, "title": "अध्याय बारा"}]
    result = book.render_research_book(*templates, entries, chapters, references, tmp_path / "hundred.docx")
    assert result["main_entries"] == 101 and result["case_entities"] == 202 and result["chapters"] == 2
    root = etree.fromstring(_parts(tmp_path / "hundred.docx")["word/document.xml"])
    text = " ".join(root.xpath(".//w:t/text()", namespaces=book.NS))
    assert "उद्यम सूत्र १०१ :" in text and "अध्याय १२ : अध्याय बारा" in text
    assert text.count("या परीक्षणप्रतीत एकूण १०१ उद्यमसूत्रे आहेत.") == 1
    assert len(root.xpath('.//w:hyperlink[starts-with(@w:anchor,"ResearchRef_")]', namespaces=book.NS)) == 404
    with pytest.raises(ValueError, match="at least one"):
        book.render_research_book(*templates, [], chapters, references, tmp_path / "empty.docx")


def test_import_has_no_template_reads_or_output_writes(monkeypatch):
    """Reload module under forbidden I/O hooks; return nothing; unexpected I/O fails the test."""
    def forbidden(*args, **kwargs):
        """Reject any captured I/O call regardless of arguments; always raise AssertionError."""
        raise AssertionError("Module import performed file I/O")

    spec = importlib.util.spec_from_file_location("research_book_import_test", book.__file__)
    module = importlib.util.module_from_spec(spec)
    with monkeypatch.context() as context:
        context.setattr(Path, "read_bytes", forbidden)
        context.setattr(Path, "write_bytes", forbidden)
        context.setattr(Path, "open", forbidden)
        spec.loader.exec_module(module)
    assert callable(module.render_research_book)


def test_verified_real_templates_structural_smoke(content, tmp_path):
    """Use local verified templates if installed; assert actual preserved XML, otherwise skip."""
    opening = Path(r"C:\Users\LENOVO\Downloads\SK_Sutras\17Nov2026\Udyam_Sutre_Sampurna_Granth_v19.docx")
    closing = Path(r"C:\Users\LENOVO\Downloads\SK_Sutras\Udyam_Sutre_Sampurna_Mukha_Anukramanika_Malaprushtha-v2.docx")
    if not opening.exists() or not closing.exists():
        pytest.skip("Verified author templates are not installed")
    result = book.render_research_book(opening, closing, *content, tmp_path / "real-template-smoke.docx")
    assert result["first85paragraphs_identical"] and result["closing_text_identical"]
    assert result["render_status"] == "NOT_RUN"
    actual_parts = _parts(tmp_path / "real-template-smoke.docx")
    actual = etree.fromstring(actual_parts["word/document.xml"]).find(book._w("body"))
    original = etree.fromstring(_parts(opening)["word/document.xml"]).find(book._w("body"))
    for old, new in zip(original.findall(book._w("p"))[:85], actual.findall(book._w("p"))[:85]):
        assert etree.tostring(old, method="c14n", exclusive=True) == etree.tostring(new, method="c14n", exclusive=True)
    baseline = Path(__file__).resolve().parents[1] / "deliverables/20261117-author-hybrid-review/Udyam_Sutre_Hybrid_Review_20261117_Centered.docx"
    if baseline.exists():
        proven_parts = _parts(baseline)
        proven = etree.fromstring(proven_parts["word/document.xml"]).find(book._w("body"))
        for old, new in zip(list(proven)[-7:-1], list(actual)[-7:-1]):
            old, new = deepcopy(old), deepcopy(new)
            for p in (old, new):
                p.attrib.pop("{" + book.W14 + "}paraId", None)
                p.attrib.pop("{" + book.W14 + "}textId", None)
            assert etree.tostring(old, method="c14n", exclusive=True) == etree.tostring(new, method="c14n", exclusive=True)
        for name in ("word/styles.xml", "word/footerConsolidationEmpty.xml"):
            assert actual_parts[name] == proven_parts[name]



@pytest.mark.parametrize('multiline',[False,True])
def test_only_multiline_original_source_quotes_get_left_alignment(templates,content,tmp_path,monkeypatch,multiline):
    """Quote alignment changes no source text, body/formula style or protected sections."""
    entries,chapters,references=content
    # A justified synthetic body slot reproduces the actual visual defect.
    parts=_parts(templates[0]);tree=etree.fromstring(parts['word/document.xml'])
    slot=tree.find(book._w('body')).findall(book._w('p'))[97]
    slot.find('./w:pPr/w:jc',book.NS).set(book._w('val'),'both')
    parts['word/document.xml']=etree.tostring(tree)
    with ZipFile(templates[0],'w') as archive:
        for name,data in parts.items():archive.writestr(name,data)
    monkeypatch.setattr(book,'OPENING_SHA256',hashlib.sha256(templates[0].read_bytes()).hexdigest())
    quote=('अद्वेष्टा सर्वभूतानां मैत्रः करुण एव च।\nनिर्ममो निरहङ्कारः समदुःखसुखः क्षमी।।12.13।।'
           if multiline else 'अथातो भक्तिजिज्ञासा।')
    references['ref-test'].update(original_text=quote,tradition='Indian')
    entries[0]['exposition']=['\n'.join(['चाचणी मराठी शब्द']*170)]
    before=deepcopy(content)
    output=tmp_path/'source-alignment.docx'
    report=book.render_research_book(*templates,entries,chapters,references,output)
    body=etree.fromstring(_parts(output)['word/document.xml']).find(book._w('body'))
    paragraphs=body.findall(book._w('p'))
    source=[p for p in paragraphs if p.xpath('.//w:t/text()',namespaces=book.NS)==quote.split('\n')]
    assert len(source)==1
    assert source[0].find('./w:pPr/w:jc',book.NS).get(book._w('val'))==('left' if multiline else 'both')
    exposition=[p for p in paragraphs if p.xpath('.//w:t/text()',namespaces=book.NS)==entries[0]['exposition'][0].split('\n')]
    assert len(exposition)==1
    assert exposition[0].find('./w:pPr/w:jc',book.NS).get(book._w('val'))=='both'
    formulas=[p for p in paragraphs if ''.join(p.xpath('.//w:t/text()',namespaces=book.NS)).startswith('॥ ')]
    assert len(formulas)==1 and formulas[0].find('./w:pPr/w:jc',book.NS).get(book._w('val'))=='center'
    protected=tree.find(book._w('body')).findall(book._w('p'))[:85]
    assert all(etree.tostring(a,method='c14n',exclusive=True)==etree.tostring(b,method='c14n',exclusive=True)
               for a,b in zip(protected,paragraphs[:85]))
    assert report['first85paragraphs_identical'] and report['closing_text_identical']
    assert content==before

"""Offline research-book export; importing this module performs no I/O.

Layout derives from logs/author-hybrid-book-20261117/assemble_hybrid.py.
Evidence is supplied by the caller: export does not verify facts or call providers.
"""

from copy import deepcopy
import hashlib
from io import BytesIO
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree


OPENING_SHA256 = "add131fb87ed22ec0eaa1b64886e530610efbb4bb7340daa2595e1239a6d6502"
CLOSING_SHA256 = "621aa70d3d81d649f2002f6bfc71e6adca0be18e655e0024f57f43a99b12dc80"
SINGLE_ENTRY_REFERENCES = frozenset({"CMP012", "CMP013", "CMP014"})
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
NS = {"w": W, "r": R}
P_ORDER = "pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange".split()
SECTION_ORDER = "headerReference footerReference footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType pgNumType cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid printerSettings sectPrChange".split()


def _w(name: str) -> str:
    """Qualify an OOXML local name; return its Clark name; no I/O or failures."""
    return "{" + W + "}" + name


def _dev(value: int) -> str:
    """Format a display integer in Devanagari; return text; no I/O or failures."""
    return str(value).translate(str.maketrans("0123456789", "०१२३४५६७८९"))


def _text(value: object, label: str) -> str:
    """Validate supplied text and return it unchanged; raise ValueError if blank."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing nonblank text: {label}")
    return value


def _url(value: object, label: str) -> str:
    """Validate a public HTTP(S) URL; return unchanged text or raise ValueError."""
    value = _text(value, label)
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"Invalid evidence URL: {label}")
    return value


def _identity(value: str) -> str:
    """Normalize a supplied identity for duplicates; return letters/numbers, never infer aliases."""
    return "".join(c for c in unicodedata.normalize("NFKC", value).casefold() if c.isalnum())


def _show_original(reference: dict) -> bool:
    """Return whether a validated record has a displayable Devanagari original.

    Western and non-Devanagari originals stay in evidence only; Marathi meaning
    and attribution are rendered instead. Parameters are a canonical reference;
    returns bool, with KeyError only if the caller bypasses record validation.
    """
    text = reference["original_text"]
    tradition = reference["tradition"].casefold()
    return ("western" not in tradition and "पाश्चात्य" not in tradition
            and bool(re.search(r"[\u0900-\u097f]", text))
            and not any(c.isalpha() and not "\u0900" <= c <= "\u097f" for c in text))


def _reference_label(reference: dict, field: str) -> str:
    """Return an optional Marathi reader label without modifying canonical evidence.

    Parameters are a validated reference and title, author, locator or tradition field name.
    Returns its supplied *_mr override, otherwise the canonical field; KeyError
    signals an incomplete record if the caller bypasses validation. Tradition
    labels Indian, Western and Other have Marathi display mappings. No I/O occurs.
    """
    if field + "_mr" in reference:
        return reference[field + "_mr"]
    if field == "tradition":
        return {"indian": "भारतीय", "western": "पाश्चात्त्य", "other": "अन्य"}.get(
            reference[field].strip().casefold(), reference[field])
    return reference.get(field + "_mr", reference[field])


def _validate(entries: list[dict], chapters: list[dict], references: dict,
              catalog: list[dict]) -> tuple[dict, list[str], dict]:
    """Validate supplied export records; return chapters, citation order and counts.

    Raises ValueError for incomplete records, duplicate identities/numbers, bad
    references or short exposition. Counts are structural, not scholarly approval.
    """
    if not isinstance(entries, list) or not entries:
        raise ValueError("Expected at least one entry")
    if not isinstance(chapters, list) or not isinstance(references, dict) or not isinstance(catalog, list):
        raise ValueError("Chapter, reference and catalog containers are invalid")
    chapter_map = {}
    for chapter in chapters:
        if not isinstance(chapter, dict):
            raise ValueError("Invalid chapter record")
        number = chapter.get("number", chapter.get("chapter"))
        if type(number) is not int or number < 1 or number in chapter_map:
            raise ValueError("Chapter numbers must be unique positive integers")
        chapter_map[number] = _text(chapter.get("title_mr", chapter.get("title")), "chapter title")
    ids, numbers, case_ids, entities, formulas = set(), set(), set(), set(), set()
    used_refs, counts, closed_chapters = [], {}, set()
    previous_chapter = None
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Invalid entry record")
        sid = _text(entry.get("id"), "entry id")
        number, chapter = entry.get("number"), entry.get("chapter")
        if sid in ids or type(number) is not int or number < 1 or number in numbers:
            raise ValueError("Entry IDs and positive numbers must be unique")
        if numbers and number <= max(numbers):
            raise ValueError("Entries must be supplied in increasing number order")
        if type(chapter) is not int or chapter not in chapter_map:
            raise ValueError(f"Unknown chapter for {sid}")
        if chapter != previous_chapter:
            if chapter in closed_chapters:
                raise ValueError("Chapter entries must be contiguous")
            closed_chapters.add(chapter)
            previous_chapter = chapter
        ids.add(sid)
        numbers.add(number)
        for field in ("title_mr", "new_sutra", "grammar_mr", "translation_mr", "application_mr", "action_mr", "summary_mr"):
            _text(entry.get(field), f"{sid}.{field}")
        formula = _identity(entry["new_sutra"])
        if not formula or formula in formulas:
            raise ValueError("Duplicate or empty formula")
        formulas.add(formula)
        exposition = entry.get("exposition")
        if not isinstance(exposition, list) or not exposition:
            raise ValueError(f"Missing exposition: {sid}")
        for paragraph in exposition:
            _text(paragraph, f"{sid}.exposition")
        tokens = " ".join(exposition).split()
        marathi_tokens = sum(bool(re.search(r"[\u0900-\u097f]", token)) for token in tokens)
        if len(tokens) < 500 or marathi_tokens < 500:
            raise ValueError(f"{sid}: at least 500 Marathi exposition tokens required")
        counts[sid] = {"words": len(tokens), "devanagari_tokens": marathi_tokens}
        refs = entry.get("references")
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) for ref in refs):
            raise ValueError(f"Missing reference IDs: {sid}")
        if len(set(refs)) != len(refs):
            raise ValueError(f"Duplicate reference IDs: {sid}")
        for ref_id in refs:
            if ref_id in SINGLE_ENTRY_REFERENCES and ref_id in used_refs:
                raise ValueError(f"Reference is limited to one entry: {ref_id}")
            ref = references.get(ref_id)
            if not isinstance(ref, dict) or ref.get("id") != ref_id:
                raise ValueError(f"Unknown or mismatched reference: {ref_id}")
            for field in ("title", "author", "locator", "original_text", "meaning_mr", "tradition"):
                _text(ref.get(field), f"{ref_id}.{field}")
            for field in ("title_mr", "author_mr", "locator_mr", "tradition_mr"):
                if field in ref:
                    _text(ref[field], f"{ref_id}.{field}")
            _url(ref.get("url"), ref_id)
            if ref_id not in used_refs:
                used_refs.append(ref_id)
        comparisons = entry.get("comparative_mr")
        if not isinstance(comparisons, list) or not comparisons:
            raise ValueError(f"Missing philosophical comparisons: {sid}")
        for comparison in comparisons:
            if not isinstance(comparison, dict) or comparison.get("source_id") not in refs:
                raise ValueError(f"Comparison lacks an entry citation: {sid}")
            _text(comparison.get("explanation_mr"), f"{sid}.comparison")
        for field in ("dos_mr", "donts_mr"):
            items = entry.get(field)
            if not isinstance(items, list) or len(items) < 3:
                raise ValueError(f"At least three {field} required: {sid}")
            for item in items:
                _text(item, f"{sid}.{field}")
        examples = entry.get("examples")
        if (not isinstance(examples, list) or len(examples) != 2 or
                any(not isinstance(case, dict) or not isinstance(case.get("kind"), str) for case in examples) or
                {case.get("kind") for case in examples} != {"positive", "caution"}):
            raise ValueError(f"One positive and one caution case required: {sid}")
        for case in examples:
            for field in ("case_id", "entity", "text_mr", "source_title"):
                _text(case.get(field), f"{sid}.case.{field}")
            _url(case.get("url"), case["case_id"])
            entity = _identity(case["entity"])
            if not entity or case["case_id"] in case_ids or entity in entities:
                raise ValueError("Duplicate case ID or entity")
            case_ids.add(case["case_id"])
            entities.add(entity)
    catalog_ids = set()
    for item in catalog:
        if not isinstance(item, dict):
            raise ValueError("Invalid proposed research record")
        sid = _text(item.get("id"), "catalog id")
        _text(item.get("title"), "catalog title")
        if sid in catalog_ids or sid in used_refs:
            raise ValueError("Proposed research must be unique and separate from cited sources")
        catalog_ids.add(sid)
        if item.get("url"):
            _url(item["url"], sid)
    return chapter_map, used_refs, counts


def render_research_book(opening_template: Path, closing_template: Path,
                         entries: list[dict], chapters: list[dict],
                         references: dict[str, dict], output: Path,
                         source_catalog: list[dict] | None = None) -> dict:
    """Render supplied research entries into the hash-bound V19 package.

    Parameters are two verified source templates, one or more ordered entries,
    chapter metadata ({number,title_mr} or {chapter,title}), canonical references,
    a new DOCX output path, and optional uncited proposed-research records.
    References may supply title_mr, author_mr, locator_mr and tradition_mr display overrides;
    canonical fields remain required and unchanged in the caller's evidence.
    Returns structural verification and provenance; pixel QA is NOT_RUN.
    Raises ValueError for invalid content/template hashes or XML invariants,
    FileExistsError for an occupied destination, and filesystem/XML/ZIP errors
    for inaccessible or malformed packages. Inputs are never modified; no
    provider, database, fact verification, or publication approval is performed.
    """
    catalog = [] if source_catalog is None else source_catalog
    chapter_map, used_refs, counts = _validate(entries, chapters, references, catalog)
    opening_template, closing_template, output = map(Path, (opening_template, closing_template, output))
    if output.suffix.lower() != ".docx":
        raise ValueError("Output must be a DOCX path")
    if output.exists():
        raise FileExistsError(output)
    if not output.parent.is_dir():
        raise FileNotFoundError(output.parent)
    original_bytes, closing_bytes = opening_template.read_bytes(), closing_template.read_bytes()
    hashes = [hashlib.sha256(raw).hexdigest() for raw in (original_bytes, closing_bytes)]
    if hashes != [OPENING_SHA256, CLOSING_SHA256]:
        raise ValueError("Template SHA256 differs from verified opening/closing baseline")
    with ZipFile(BytesIO(original_bytes)) as archive:
        original_parts = {name: archive.read(name) for name in archive.namelist()}
    with ZipFile(BytesIO(closing_bytes)) as archive:
        close_root = etree.fromstring(archive.read("word/document.xml"))
        close_styles = etree.fromstring(archive.read("word/styles.xml"))
    root = etree.fromstring(original_parts["word/document.xml"])
    body = root.find(_w("body"))
    original_paragraphs = body.findall(_w("p"))
    original_section = deepcopy(body.find(_w("sectPr")))
    slots = {name: deepcopy(original_paragraphs[index]) for name, index in
             (("chapter", 85), ("verse", 86), ("heading", 88), ("body", 97), ("label", 104))}
    for element in list(body):
        body.remove(element)
    for paragraph in original_paragraphs[:85]:
        body.append(deepcopy(paragraph))
    relroot = etree.fromstring(original_parts["word/_rels/document.xml.rels"])
    rel_ids = {element.get("Id") for element in relroot}
    bookmarks = {element.get(_w("name")) for element in body.iter(_w("bookmarkStart"))}
    bookmark_id = max([int(e.get(_w("id"))) for e in body.iter(_w("bookmarkStart"))] + [999])
    ref_numbers = {sid: i for i, sid in enumerate(used_refs, 1)}
    all_cases = [case for entry in entries for case in entry["examples"]]
    case_numbers = {case["case_id"]: i for i, case in enumerate(all_cases, len(used_refs) + 1)}

    def paragraph(kind, text, lead=None, page_break=False, align=None):
        """Clone a style slot with supplied text; return appended XML; XML errors propagate."""
        p = deepcopy(slots[kind])
        pp = p.find(_w("pPr"))
        if pp is None:
            pp = etree.Element(_w("pPr"))
            p.insert(0, pp)
        for tag in ("numPr", "ind", "pBdr", "pageBreakBefore", "keepNext", "keepLines", "outlineLvl"):
            for element in pp.findall(_w(tag)):
                pp.remove(element)
        if page_break:
            etree.SubElement(pp, _w("pageBreakBefore")).set(_w("val"), "1")
        if kind in {"chapter", "verse", "heading"}:
            etree.SubElement(pp, _w("keepNext")).set(_w("val"), "1")
        if kind in {"chapter", "heading"}:
            etree.SubElement(pp, _w("outlineLvl")).set(_w("val"), "0" if kind == "chapter" else "2")
        if align:
            for element in pp.findall(_w("jc")):
                pp.remove(element)
            etree.SubElement(pp, _w("jc")).set(_w("val"), align)
        runs = p.findall(_w("r"))
        template = deepcopy(runs[1] if kind in {"body", "label"} and len(runs) > 1 else runs[0])
        label_template = deepcopy(runs[0])
        for element in list(p):
            if element.tag != _w("pPr"):
                p.remove(element)
        chunks = [(label_template, lead + " : "), (template, text)] if lead else [(template, text)]
        for run, content in chunks:
            for element in list(run):
                if element.tag != _w("rPr"):
                    run.remove(element)
            rp = run.find(_w("rPr"))
            if rp is None:
                rp = etree.SubElement(run, _w("rPr"))
            fonts = rp.find(_w("rFonts"))
            if fonts is None:
                fonts = etree.SubElement(rp, _w("rFonts"))
            for key in ("ascii", "hAnsi", "eastAsia", "cs"):
                fonts.set(_w(key), "Nirmala UI")
            for line_number, line in enumerate(content.split("\n")):
                if line_number:
                    etree.SubElement(run, _w("br"))
                node = etree.SubElement(run, _w("t"))
                node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                node.text = line
            p.append(run)
        body.append(p)
        return p

    def bookmark(p, name):
        """Attach a unique named destination to paragraph p; return None; reject collisions."""
        nonlocal bookmark_id
        if name in bookmarks:
            raise ValueError(f"Bookmark collision: {name}")
        bookmarks.add(name)
        bookmark_id += 1
        start = etree.Element(_w("bookmarkStart"))
        start.set(_w("id"), str(bookmark_id))
        start.set(_w("name"), name)
        end = etree.Element(_w("bookmarkEnd"))
        end.set(_w("id"), str(bookmark_id))
        p.insert(1, start)
        p.append(end)

    def relation(kind, target):
        """Append a collision-free relationship; return its ID; XML errors propagate."""
        index = len(rel_ids) + 1
        while f"rIdResearch{index}" in rel_ids:
            index += 1
        rid = f"rIdResearch{index}"
        rel_ids.add(rid)
        rel = etree.SubElement(relroot, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
        rel.set("Id", rid)
        rel.set("Type", R + "/" + kind)
        rel.set("Target", target)
        if kind == "hyperlink":
            rel.set("TargetMode", "External")
        return rid

    def link(p, text, anchor=None, url=None):
        """Append a styled citation/URL link; return None; require exactly one target."""
        if bool(anchor) == bool(url):
            raise ValueError("Hyperlink requires exactly one target")
        hyperlink = etree.SubElement(p, _w("hyperlink"))
        hyperlink.set(_w("anchor") if anchor else "{" + R + "}id", anchor or relation("hyperlink", url))
        run = etree.SubElement(hyperlink, _w("r"))
        rp = etree.SubElement(run, _w("rPr"))
        etree.SubElement(rp, _w("color")).set(_w("val"), "0563C1")
        etree.SubElement(rp, _w("u")).set(_w("val"), "single")
        etree.SubElement(rp, _w("sz")).set(_w("val"), "20")
        etree.SubElement(rp, _w("szCs")).set(_w("val"), "20")
        etree.SubElement(run, _w("t")).text = text

    paragraph("chapter", "उद्यमसूत्रे वाचनक्रम")
    paragraph("body", "मूळ स्रोतांचा अर्थ, तुलनात्मक चिंतन आणि आधुनिक उद्यमातील उपयोग स्वतंत्रपणे दिले आहेत. हा लेखक व विद्वान यांच्या परीक्षणासाठी संशोधन मसुदा आहे.")
    paragraph("body", f"या परीक्षणप्रतीत एकूण {_dev(len(entries))} उद्यमसूत्रे आहेत.")
    active_chapters = list(dict.fromkeys(entry["chapter"] for entry in entries))
    for chapter in active_chapters:
        p = paragraph("label", "", lead=f"अध्याय {_dev(chapter)}")
        link(p, chapter_map[chapter], anchor=f"ResearchChapter_{chapter}")
    previous_chapter = None
    for entry in entries:
        chapter, number = entry["chapter"], entry["number"]
        if chapter != previous_chapter:
            p = paragraph("chapter", f"अध्याय {_dev(chapter)} : {chapter_map[chapter]}", page_break=True)
            bookmark(p, f"ResearchChapter_{chapter}")
        p = paragraph("chapter", f"उद्यम सूत्र {_dev(number)} : {entry['title_mr']}", page_break=chapter == previous_chapter)
        p.find("./w:pPr/w:outlineLvl", NS).set(_w("val"), "1")
        bookmark(p, f"ResearchSutra_{number}")
        previous_chapter = chapter
        paragraph("verse", "॥ " + entry["new_sutra"].strip(" ।॥") + " ॥", align="center")
        paragraph("heading", "१. पदच्छेद अन्वय आणि मराठी अर्थ")
        paragraph("body", entry["grammar_mr"])
        paragraph("label", entry["translation_mr"], lead="मराठी अर्थ")
        paragraph("heading", "२. मूळ स्रोत आणि तुलनात्मक तत्त्वचिंतन")
        for sid in entry["references"]:
            ref, n = references[sid], ref_numbers[sid]
            p = paragraph("label", " — ".join(_reference_label(ref, field) for field in ("author", "title", "locator")), lead=_reference_label(ref, "tradition"))
            link(p, f"\u00a0[संदर्भ\u00a0{_dev(n)}]", anchor=f"ResearchRef_{n}")
            if _show_original(ref):
                paragraph("body", ref["original_text"],
                          align="left" if "\n" in ref["original_text"] else None)
            paragraph("label", ref["meaning_mr"], lead="मूळ आशय")
        for comparison in entry["comparative_mr"]:
            sid = comparison["source_id"]
            p = paragraph("label", comparison["explanation_mr"], lead="तुलनात्मक चिंतन — " + _reference_label(references[sid], "author"))
            link(p, f"\u00a0[संदर्भ\u00a0{_dev(ref_numbers[sid])}]", anchor=f"ResearchRef_{ref_numbers[sid]}")
        paragraph("heading", "३. तत्त्वनिरूपण आणि उद्योजकीय व्यवहार")
        for block in entry["exposition"]:
            paragraph("body", block)
        paragraph("heading", "४. सत्य व ऐतिहासिक दृष्टांत")
        for case in entry["examples"]:
            paragraph("label", case["entity"], lead="यशस्वी दाखला" if case["kind"] == "positive" else "सावधगिरीचा दाखला")
            p = paragraph("body", case["text_mr"])
            n = case_numbers[case["case_id"]]
            link(p, f"\u00a0[संदर्भ\u00a0{_dev(n)}]", anchor=f"ResearchRef_{n}")
        paragraph("heading", "५. प्रत्यक्ष आचारसंहिता")
        for field, label in (("dos_mr", "काय करावे"), ("donts_mr", "काय टाळावे")):
            paragraph("label", " ".join(f"{_dev(i)}) {item}" for i, item in enumerate(entry[field], 1)), lead=label)
        for field, label in (("application_mr", "व्यवस्थापनातील उपयोग"), ("action_mr", "कृतीमंत्र"), ("summary_mr", "सारबोध")):
            paragraph("label", entry[field], lead=label)
    paragraph("chapter", "संदर्भसूची", page_break=True)
    for sid in used_refs:
        ref, n = references[sid], ref_numbers[sid]
        label = " — ".join(_reference_label(ref, field) for field in ("author", "title", "locator"))
        p = paragraph("label", label + " — " + _reference_label(ref, "tradition"), lead=_dev(n), align="left")
        bookmark(p, f"ResearchRef_{n}")
        link(p, " — " + ref["url"], url=ref["url"])
    for case in all_cases:
        n = case_numbers[case["case_id"]]
        p = paragraph("label", case["source_title"], lead=_dev(n), align="left")
        bookmark(p, f"ResearchRef_{n}")
        link(p, " — " + case["url"], url=case["url"])
    if source_catalog:
        paragraph("chapter", "पुढील अभ्यासासाठी संदर्भग्रंथ", page_break=True)
        paragraph("body", "पुढील स्रोत भावी संशोधनासाठी सुचविले आहेत. त्यांचा वरील दाव्यांसाठी उद्धृत पुरावा म्हणून वापर केलेला नाही.")
        for item in source_catalog:
            p = paragraph("body", " — ".join(str(item[key]) for key in ("author", "title", "locator") if item.get(key)), align="left")
            if item.get("url"):
                link(p, " — " + item["url"], url=item["url"])

    # Preserve the established closing layout, including inherited font defaults.
    boundary = etree.SubElement(body, _w("p"))
    etree.SubElement(boundary, _w("pPr")).append(deepcopy(original_section))
    close_body = close_root.find(_w("body"))
    close_paragraphs = close_body.findall(_w("p"))[39:45]
    default_r = close_styles.find("./w:docDefaults/w:rPrDefault/w:rPr", NS)
    closing_style = etree.Element(_w("style"))
    closing_style.set(_w("type"), "paragraph")
    closing_style.set(_w("styleId"), "ClosingSourceNormal")
    etree.SubElement(closing_style, _w("name")).set(_w("val"), "Closing Source Normal")
    closing_style.append(deepcopy(close_styles.find("./w:docDefaults/w:pPrDefault/w:pPr", NS)))
    closing_style.append(deepcopy(default_r))
    closing_start = len(body)
    for cp in close_paragraphs:
        p = deepcopy(cp)
        pp = p.find(_w("pPr"))
        if pp is None:
            pp = etree.Element(_w("pPr"))
            p.insert(0, pp)
        ps = pp.find(_w("pStyle"))
        if ps is None:
            ps = etree.Element(_w("pStyle"))
            pp.insert(0, ps)
        ps.set(_w("val"), "ClosingSourceNormal")
        pr = pp.find(_w("rPr"))
        if pr is None:
            pr = etree.SubElement(pp, _w("rPr"))
        if pr.find(_w("rFonts")) is None:
            pr.append(deepcopy(default_r.find(_w("rFonts"))))
        for run in p.findall(_w("r")):
            rp = run.find(_w("rPr"))
            if rp is None:
                rp = etree.Element(_w("rPr"))
                run.insert(0, rp)
            for default in default_r:
                if rp.find(default.tag) is None:
                    rp.append(deepcopy(default))
        body.append(p)
    close_section = deepcopy(close_body.find(_w("sectPr")))
    close_section.find(_w("pgMar")).set(_w("top"), "1400")
    for element in list(close_section):
        if element.tag in {_w("headerReference"), _w("footerReference"), _w("type")}:
            close_section.remove(element)
    etree.SubElement(close_section, _w("type")).set(_w("val"), "nextPage")
    footer = etree.Element(_w("footerReference"))
    footer.set(_w("type"), "default")
    footer.set("{" + R + "}id", relation("footer", "footerConsolidationEmpty.xml"))
    close_section.insert(0, footer)
    body.append(close_section)
    used_ids = {p.get("{" + W14 + "}paraId") for p in body[:85]}
    next_id = 0x100000
    order = {_w(name): i for i, name in enumerate(P_ORDER)}
    for element in list(body)[85:]:
        for p in element.iter(_w("p")):
            while format(next_id, "08X") in used_ids:
                next_id += 1
            value = format(next_id, "08X")
            used_ids.add(value)
            next_id += 1
            p.set("{" + W14 + "}paraId", value)
            p.attrib.pop("{" + W14 + "}textId", None)
            pp = p.find(_w("pPr"))
            if pp is not None:
                pp[:] = sorted(pp, key=lambda node: order.get(node.tag, 999))
    section_order = {_w(name): i for i, name in enumerate(SECTION_ORDER)}
    close_section[:] = sorted(close_section, key=lambda node: section_order.get(node.tag, 999))
    if any(etree.tostring(a, method="c14n", exclusive=True) != etree.tostring(b, method="c14n", exclusive=True)
           for a, b in zip(original_paragraphs[:85], body.findall(_w("p"))[:85])):
        raise ValueError("Protected opening XML changed")
    source_text = [p.xpath(".//w:t/text()", namespaces=NS) for p in close_paragraphs]
    output_text = [p.xpath(".//w:t/text()", namespaces=NS) for p in list(body)[closing_start:closing_start + 6]]
    if len(close_paragraphs) != 6 or source_text != output_text:
        raise ValueError("Protected closing text changed")
    new_parts = dict(original_parts)
    styles = etree.fromstring(original_parts["word/styles.xml"])
    styles.append(closing_style)
    for name, tree in (("word/document.xml", root), ("word/styles.xml", styles), ("word/_rels/document.xml.rels", relroot)):
        new_parts[name] = etree.tostring(tree, xml_declaration=True, encoding="UTF-8", standalone=True)
    new_parts["word/footerConsolidationEmpty.xml"] = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p/></w:ftr>'
    content_types = etree.fromstring(original_parts["[Content_Types].xml"])
    override = etree.SubElement(content_types, "{http://schemas.openxmlformats.org/package/2006/content-types}Override")
    override.set("PartName", "/word/footerConsolidationEmpty.xml")
    override.set("ContentType", "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml")
    new_parts["[Content_Types].xml"] = etree.tostring(content_types, xml_declaration=True, encoding="UTF-8", standalone=True)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, data in new_parts.items():
            archive.writestr(name, data)
    payload = buffer.getvalue()
    created = False
    try:
        with output.open("xb") as stream:
            created = True
            stream.write(payload)
    except FileExistsError:
        raise
    except OSError:
        if created:
            output.unlink(missing_ok=True)
        raise
    return {"output": str(output), "sha256": hashlib.sha256(payload).hexdigest(),
            "status": "DRAFT_PENDING_VISUAL_AND_SCHOLAR_REVIEW", "main_entries": len(entries),
            "chapters": len(active_chapters), "case_entities": len(all_cases),
            "cited_references": used_refs, "proposed_research_count": len(source_catalog or []),
            "word_counts": counts, "source_hashes": {"opening": hashes[0], "closing": hashes[1]},
            "first85paragraphs_identical": True, "closing_text_identical": True,
            "centered_main_formulas": len(entries), "render_status": "NOT_RUN",
            "factual_verification": "CALLER_SUPPLIED_NOT_PERFORMED_BY_EXPORTER",
            "author_approval": False, "publication": False}

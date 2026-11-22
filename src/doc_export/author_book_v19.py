"""Render local review drafts into the author's v19 Word layout."""

from copy import deepcopy
import os
from pathlib import Path
import re
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from src.orchestration.book_acceptance import sutra_shape_issues


SOURCE_LABELS = {
    "DOC-01": "संदर्भग्रंथ ‘श्रीमद् उद्यम सूत्राणि’",
    "DOC-02": "कार्यावृत्ती १७",
    "DOC-03": "पूर्वीचा मसुदा (कार्यावृत्ती ०५)",
    "DOC-04": "संत तुकाराम विचारसंग्रह",
}


def reader_text(value: str) -> str:
    """Render internal source references in readable Marathi book prose.

    ``value`` is a generated display field. Return its words with document
    titles in place of internal IDs, without SHA fingerprints or manual line
    breaks. Non-text raises TypeError; inspect the raw chapter JSON for source
    provenance if a display label is unexpected. The raw draft stays intact.
    """
    if not isinstance(value, str):
        raise TypeError("Reader-facing book field must be text")
    result = re.sub(r",?\s*source_version\s+[0-9a-f]{64}\b", "", value, flags=re.IGNORECASE)
    result = re.sub(r"\bDOC-0[1-4]\b", lambda match: SOURCE_LABELS[match.group()], result)
    if re.search(r"\b(?:DOC-[0-9]{2}|[0-9a-f]{64})\b", result):
        raise ValueError("Unmapped internal source reference in book prose")
    return re.sub(r"\s*\n\s*", " ", result)


def render_book(template: Path, chapters: list[dict[str, Any]], output: Path,
                reader_first: bool = False) -> Path:
    """Preserve all v19 XML through its ninth page, then append chapter copies.

    The template must have its eighth explicit page break at paragraph 108.
    Returns the local DOCX path. Invalid template boundaries, >19 new chapters,
    or a long verse raise before saving; inspect prefix XML, count and verse.
    This exporter does not approve or publish any draft.
    With reader_first=True, require explicit edited reader fields and place
    meaning and explanation before brief sources, omitting scholarly apparatus.
    """
    source = Document(template)
    paragraphs = source.paragraphs
    breaks = [i for i, p in enumerate(paragraphs) if p._p.xpath('.//w:br[@w:type="page"]')]
    if len(breaks) < 8 or breaks[7] != 108 or not 1 <= len(chapters) <= 19:
        raise ValueError("v19 nine-page prefix or chapter count changed")
    for number, chapter in enumerate(chapters, 2):
        failures = sutra_shape_issues(chapter.get("new_sutra"))
        if failures:
            raise ValueError(f"Chapter {number} cannot enter Word book: {failures}")
    prefix = [deepcopy(p._p) for p in paragraphs[:109]]
    chapter_layout = [deepcopy(p._p) for p in paragraphs[85:109]]
    for element in list(source.element.body):
        if element.tag != qn("w:sectPr"):
            source.element.body.remove(element)
    for element in prefix:
        source.element.body.insert(len(source.element.body)-1, element)

    def add(template_index: int, text: str, plain: bool = False) -> None:
        """Append one author-styled paragraph with new displayed text.

        ``template_index`` identifies a chapter-layout slot and ``text`` is
        chapter prose. Returns None; missing styled runs raise ValueError.
        Inspect the original paragraph's run colors and the rendered page if
        a lead or body appears with the wrong emphasis.
        Plain paragraphs suppress inherited bullets and use left alignment.
        """
        text = reader_text(text)
        element = deepcopy(chapter_layout[template_index])
        if reader_first and template_index in {18, 19, 21}:
            properties = element.find(qn("w:pPr"))
            if properties is None:
                properties = OxmlElement("w:pPr")
                element.insert(0, properties)
            keep = properties.find(qn("w:keepNext"))
            if keep is None:
                keep = OxmlElement("w:keepNext")
                properties.append(keep)
            keep.set(qn("w:val"), "1")
        if plain:
            properties = element.find(qn("w:pPr"))
            if properties is None:
                properties = OxmlElement("w:pPr")
                element.insert(0, properties)
            for tag in ("w:numPr", "w:jc", "w:ind", "w:spacing"):
                for old in properties.findall(qn(tag)):
                    properties.remove(old)
            numbering = OxmlElement("w:numPr")
            number_id = OxmlElement("w:numId")
            number_id.set(qn("w:val"), "0")
            numbering.append(number_id)
            properties.append(numbering)
            alignment = OxmlElement("w:jc")
            alignment.set(qn("w:val"), "left")
            properties.append(alignment)
            spacing = OxmlElement("w:spacing")
            spacing.set(qn("w:after"), "120")
            properties.append(spacing)
        runs = element.xpath('.//w:r')
        if not runs:
            raise ValueError("Author template paragraph lacks a styled run")
        prose = template_index in {4, 5, 6, 8, 9, 10, 12, 17, 19, 20, 21, 22}
        if prose and len(runs) < 2:
            raise ValueError("Author template paragraph lacks a separate body run")
        for run in runs[2 if prose else 1:]:
            run.getparent().remove(run)
        if prose:
            if template_index == 12 or " : " not in text:
                lead, body = "", text
            else:
                prefix, body = text.split(" : ", 1)
                lead = prefix + " : "
            segments = ((runs[0], lead), (runs[1], body))
        else:
            segments = ((runs[0], text),)
        for run, segment in segments:
            for child in list(run):
                if child.tag != qn("w:rPr"):
                    run.remove(child)
            for line_number, line in enumerate(segment.split("\n")):
                if line_number:
                    run.append(OxmlElement("w:br"))
                item = OxmlElement("w:t")
                item.text = line
                run.append(item)
        source.element.body.insert(len(source.element.body)-1, element)

    for index, chapter in enumerate(chapters):
        number = index + 2
        display_number = str(number).translate(str.maketrans("0123456789", "०१२३४५६७८९"))
        if chapter.get("number") != number:
            raise ValueError("Reader chapters must be consecutive from one")
        if index:
            boundary = deepcopy(chapter_layout[23])
            source.element.body.insert(len(source.element.body)-1, boundary)
        add(0, f"अध्याय {display_number} : {chapter['title_mr']}")
        verse = chapter["new_sutra"].strip(" ।॥")
        add(1, f"उद्यम सूत्र {display_number} : ॥ {verse} ॥")
        if reader_first:
            # Editorial reader fields are explicit; never silently shorten a
            # scholarly field or alter the saved agent draft during export.
            add(3, "१. सोपा मराठी अर्थ")
            add(12, chapter["reader_translation_mr"], plain=True)
            add(11, "२. आपल्या व्यवसायात याचा अर्थ")
            for block in chapter["reader_explanation_mr"].split("\n\n"):
                if block.strip():
                    add(12, block.strip(), plain=True)
            add(7, "३. मूळ सूत्रांशी नाते — थोडक्यात")
            for key, label in (("narada_sutra", "नारद भक्तीसूत्र"),
                               ("shandilya_sutra", "शांडिल्य भक्तीसूत्र")):
                item = chapter[key]
                source_verse = item["text"].strip(" ।॥")
                add(8, label + " : ॥ " + source_verse + " ॥ — " + item["brief_meaning_mr"], plain=True)
            add(12, chapter["reader_source_link_mr"], plain=True)
            add(15, "४. अनुभवातून शिकूया")
            for example in chapter["examples"]:
                label = "यातून शिकूया" if example["kind"] == "positive" else "ही चूक टाळूया"
                add(17, label + " — " + example["business"] + " : " + example["description_mr"]
                    + " (स्रोत : " + example["source"] + ")", plain=True)
            add(18, "५. आचरणात आणण्यासाठी")
            for item in chapter["reader_dos_mr"]:
                add(19, "करावे : " + item)
            for item in chapter["reader_donts_mr"]:
                add(21, "टाळावे : " + item)
            add(22, "स्वतःला विचारूया : " + chapter["reflection_mr"], plain=True)
            add(22, "आजची छोटी कृती : " + chapter["reader_action_mr"], plain=True)
            continue
        add(3, "१. पदच्छेद, अन्वय आणि मराठी अर्थ")
        add(4, "पदच्छेद : " + chapter["padaccheda"])
        add(5, "अन्वय : " + chapter["anvaya"])
        add(5, "निरुक्त : " + chapter["nirukta"])
        add(6, "मराठी अर्थ : " + chapter["translation_mr"])
        add(7, "२. मूळ भक्तीसूत्र आधार (नारद व शांडिल्य समन्वय)")
        add(8, "देवर्षी नारद भक्तीसूत्र : ॥ " + chapter["narada_sutra"]["text"] + " ॥ — अर्थ : " + chapter["narada_sutra"]["brief_meaning_mr"])
        add(9, "महर्षी शांडिल्य भक्तीसूत्र : ॥ " + chapter["shandilya_sutra"]["text"] + " ॥ — अर्थ : " + chapter["shandilya_sutra"]["brief_meaning_mr"])
        add(10, "समन्वय मीमांसा : " + chapter["derivation_mr"])
        add(11, "३. तत्त्वनिरूपण उद्योजकीय मानसशास्त्र आणि भारतीय ज्ञानपरंपरा")
        for block in re.split(r"\n\s*\n+", chapter["explanation_mr"]):
            if block.strip():
                add(12, block.strip())
        add(15, "४. सत्य आणि ऐतिहासिक दृष्टांत")
        for example in chapter["examples"]:
            label = "यशस्वी दाखला" if example["kind"] == "positive" else "सावधगिरीचा दाखला"
            add(17, label + " — " + example["person"] + " — " + example["business"] + " : " + example["description_mr"] + " (स्रोत : " + example["source"] + ")")
        positive = next(example for example in chapter["examples"] if example["kind"] == "positive")
        cautionary = next(example for example in chapter["examples"] if example["kind"] == "cautionary")
        add(18, "५. प्रत्यक्ष आचारसंहिता (Do's & Don'ts) आणि यश अपयश दाखले")
        add(19, "काय करावे : " + chapter["dos_mr"][0])
        for item in chapter["dos_mr"][1:]:
            add(19, item)
        add(20, "यशस्वी उदाहरण : " + positive["person"] + " — " + positive["business"] + ". " + positive["description_mr"])
        add(21, "काय टाळावे : " + chapter["donts_mr"][0])
        for item in chapter["donts_mr"][1:]:
            add(21, item)
        add(22, "सावधगिरीचे उदाहरण : " + cautionary["person"] + " — " + cautionary["business"] + ". " + cautionary["description_mr"])
        add(22, "चिंतन : " + chapter["reflection_mr"])
        add(22, "पुढील कृती : " + chapter["reader_action_mr"])
    output.parent.mkdir(parents=True, exist_ok=True)
    building = output.with_name(output.stem + ".building.docx")
    source.save(building)
    check = Document(building)
    original = Document(template)
    for old, new in zip(original.paragraphs[:109], check.paragraphs[:109]):
        if old._p.xml != new._p.xml:
            raise ValueError("Author front-matter XML changed")
    os.replace(building, output)
    return output

"""Observable book council and original-front-matter regression checks."""

import json
from pathlib import Path

import pytest
from docx import Document

from src.doc_export.author_book_v19 import reader_text, render_book
from src.orchestration.book_acceptance import check_chapter, identity_aliases
from src.orchestration.book_council import BookCouncil, VOICES
from scripts.audit_book_v19 import reply_coverage


def test_provider_object_accepts_markdown_wrapper_but_rejects_two_objects():
    """One complete provider answer survives wrapper text without merging drafts."""
    from scripts.run_book_council_v19 import parse_object

    assert parse_object('```json\n{"verdict":"PASS"}\n```\nDone.') == {"verdict": "PASS"}
    with pytest.raises(ValueError):
        parse_object('{"one":1} {"two":2}')


def test_business_aliases_cover_parentheses_and_company_suffix():
    """A Latin alias in Marathi display text blocks a later company variant."""
    assert identity_aliases("ऍपल (Apple)") & identity_aliases("Apple Inc.")


def test_reply_audit_detects_an_unanswered_peer():
    """A three-way discussion cannot pass on a generic or partial reply."""
    assert reply_coverage({"to_shandilya": "answered", "to_researcher": "answered"}) == {
        "shandilya", "researcher"}
    assert reply_coverage([{"from": "narada", "answer": "considered"},
                           {"challenge_from": "researcher", "answer": "considered"},
                           {"to": "shandilya_via_sutrakar", "answer": "considered"}]) == {
        "narada", "researcher", "shandilya"}
    assert reply_coverage("I agree with everyone") == set()


def test_reader_prose_hides_internal_fingerprint_and_names_source():
    """The Word display keeps readable provenance without audit-only tokens."""
    displayed = reader_text("DOC-02, परिच्छेद २५, source_version " + "a" * 64 + "\nस्वतंत्र रचना")
    assert "कार्यावृत्ती १७" in displayed
    assert "source_version" not in displayed
    assert "DOC-02" not in displayed
    assert "\n" not in displayed
    with pytest.raises(ValueError):
        reader_text("DOC-99")


def test_long_sanskrit_sentence_fails_short_sutra_gate():
    """Reject lines longer than the author's compact model even with few spaces."""
    source = {"narada_sutra": {"text": "न"}, "shandilya_sutra": {"text": "श"}}
    result = check_chapter({"new_sutra": "धर्म" * 25}, source, set(), set())
    assert any("32 characters" in issue for issue in result["issues"])
    result = check_chapter({"new_sutra": "कर्तव्यानपायेन विक्षेपहेतून् हित्वैकाधारे निष्ठा॥"}, source, set(), set())
    assert any("32 characters" in issue for issue in result["issues"])
    result = check_chapter({"new_sutra": "सा परमानुरागरूपा उद्यमनिष्ठा॥"}, source, set(), set())
    assert not any("New Sanskrit sutra" in issue for issue in result["issues"])


def test_twenty_sutra_cap_and_gradual_closure(tmp_path):
    """The revised cap blocks chapter 21 before any credential or provider call."""
    from scripts.audit_book_v19 import audit_book
    from scripts.run_book_council_v19 import ROOT, run_book

    roadmap = json.loads((ROOT / "data/book_roadmap_20.json").read_text(encoding="utf-8"))
    assert [item["number"] for item in roadmap] == list(range(1, 21))
    assert [item["reader_stage"] for item in roadmap[15:]] == [
        "बाह्य विश्वासाची सुरुवात", "मूल्य टिकविणारी वाढ",
        "व्यवसायाचा व्यापक परिणाम", "विश्वाशी जबाबदार संबंध",
        "समारोप आणि पुढील पिढ्यांची जबाबदारी"]
    assert "अथातो उद्यमजिज्ञासा" in roadmap[-1]["reader_question"]
    template = Path(r"C:/Users/LENOVO/Downloads/Udyam_Sutre_Sampurna_Granth_v19.docx")
    with pytest.raises(ValueError, match="nineteen new chapters"):
        run_book(tmp_path, template, 21)
    with pytest.raises(ValueError, match="at most 20"):
        audit_book(tmp_path, template, 21)
    if template.exists():
        with pytest.raises(ValueError, match="chapter count"):
            render_book(template, [{}] * 20, tmp_path / "too-many.docx")
    council = BookCouncil(tmp_path / "cap.db", {name: lambda payload: {} for name in VOICES},
                          lambda payload: {})
    with pytest.raises(ValueError, match="between 2 and 20"):
        council.run(21, {"reader_question": "closure"}, {}, [], [])


def test_all_four_voices_challenge_and_validator_remains_separate(tmp_path):
    """Every voice answers a challenge and only the fifth sees the final draft."""
    calls = []

    def make_voice(name):
        """Build one role callback with observable cross-voice context."""
        def answer(request):
            """Record a role turn and return stage-specific evidence."""
            stage = request["stage"]
            calls.append((name, stage))
            if stage == "challenge":
                assert set(request["discussion"]["position"]) == set(VOICES)
                if name == "narada" and "repair_feedback" not in request:
                    return {"challenges": {"Shandilya Specialist": "Please cite the evidence"}}
                if name == "shandilya":
                    return {peer: "Please cite the evidence" for peer in VOICES if peer != name}
                if name == "sutrakar":
                    return {"challenges": {peer: {"question": "Please cite the evidence"}
                                           for peer in VOICES if peer != name}}
                return {"challenges": {peer: f"{name} asks {peer} for evidence" for peer in VOICES if peer != name}}
            if stage == "reply":
                assert set(request["discussion"]["challenge"]) == set(VOICES)
                peers = [peer for peer in VOICES if peer != name]
                if name == "narada" and "repair_feedback" not in request:
                    return {"answers": {peer: "answered with evidence" for peer in peers[:2]}}
                if name == "shandilya":
                    return {peer: "answered with evidence" for peer in peers}
                return {"answers": {peer: "answered with evidence" for peer in peers}}
            if stage == "proposal":
                return {"proposed_sutra": "उद्यमेन विवेकः", "derivation": "सेतू"}
            if stage == "composition":
                assert set(request["peer_review"]) == set(VOICES[:-1])
                return {"new_sutra": "उद्यमेन विवेकः", "padaccheda": "उद्यमेन विवेकः",
                        "anvaya": "विवेकः उद्यमेन", "nirukta": "विवेक", "translation_mr": "विवेक",
                        "derivation_mr": "सेतू", "explanation_mr": "उद्योग", "narada_sutra": {},
                        "shandilya_sutra": {}, "examples": [], "dos_mr": [], "donts_mr": [],
                        "reflection_mr": "विचार", "reader_action_mr": "कृती"}
            return {"evidence": f"{name} {stage}"}
        return answer

    def validate(request):
        """Require a completed council record before independent judgment."""
        assert request["draft"]["new_sutra"] == "उद्यमेन विवेकः"
        assert set(request["discussion"]) == {"position", "challenge", "reply"}
        calls.append(("validator", "independent_review"))
        return {"verdict": "REVIEW_REQUIRED", "issues": ["scholar check"]}

    council = BookCouncil(tmp_path / "council.db", {name: make_voice(name) for name in VOICES}, validate)
    args = (2, {"reader_question": "How to begin?"}, {"narada_sutra": {}, "shandilya_sutra": {}}, [], [])
    result = council.run(*args)
    assert result["review"]["verdict"] == "REVIEW_REQUIRED"
    assert set(result["discussion"]["reply"]["shandilya"]["answers"]) == set(VOICES) - {"shandilya"}
    assert len(calls) == 20
    council.run(*args)
    assert len(calls) == 20


def test_long_proposal_stops_before_paid_peer_review_or_composition(tmp_path):
    """Two failed proposal attempts stop downstream calls before full drafting."""
    calls = []

    def make_voice(name):
        """Return minimal stage answers and record any expensive downstream turn."""
        def answer(request):
            """Supply valid discussion rounds and an overlong proposal only."""
            stage = request["stage"]
            calls.append(stage)
            peers = [peer for peer in VOICES if peer != name]
            if stage == "challenge":
                return {"challenges": {peer: "What is the evidence?" for peer in peers}}
            if stage == "reply":
                return {"answers": {peer: "The evidence is in the source." for peer in peers}}
            if stage == "proposal":
                return {"proposed_sutra": "कर्तव्यानपायेन विक्षेपहेतून् हित्वैकाधारे निष्ठा॥"}
            if stage == "position":
                return {"thesis": "business focus"}
            raise AssertionError(f"Unexpected downstream stage: {stage}")
        return answer

    council = BookCouncil(tmp_path / "short.db", {name: make_voice(name) for name in VOICES},
                          lambda request: (_ for _ in ()).throw(AssertionError("validator called")))
    with pytest.raises(ValueError, match="Proposal fails short-sutra gate"):
        council.run(2, {"reader_question": "How to begin?"},
                    {"registered_knowledge": {"passages": []}}, [], [])
    assert calls.count("proposal") == 2
    assert "peer_review" not in calls and "composition" not in calls


def test_marathi_length_and_reused_examples_block(tmp_path):
    """A short explanation and a repeated business cannot enter review."""
    source = {"narada_sutra": {"text": "नारद"}, "shandilya_sutra": {"text": "शांडिल्य"}}
    chapter = {"new_sutra": "उद्यमेन विवेकः", "narada_sutra": {"text": "नारद", "brief_meaning_mr": "अर्थ"},
               "shandilya_sutra": {"text": "शांडिल्य", "brief_meaning_mr": "अर्थ"},
               "translation_mr": "उद्योगात विवेक", "padaccheda": "उद्यमेन विवेकः", "anvaya": "विवेकः उद्यमेन",
               "nirukta": "विवेक", "derivation_mr": "सेतू", "explanation_mr": "उद्योग विवेक" * 10,
               "reflection_mr": "चिंतन", "reader_action_mr": "कृती",
               "examples": [{"person": "A", "business": "Repeated Co", "description_mr": "कथा", "source": "source"},
                            {"person": "B", "business": "Fresh Co", "description_mr": "कथा", "source": "source"}],
               "dos_mr": ["एक", "दोन", "तीन"], "donts_mr": ["एक", "दोन", "तीन"]}
    report = check_chapter(chapter, source, {"repeated co"}, set())
    assert report["status"] == "NEEDS_REVISION"
    assert any("500" in issue for issue in report["issues"])
    assert any("Repeated" in issue for issue in report["issues"])
    assert any("positive and a cautionary" in issue for issue in report["issues"])


def test_v19_front_xml_unchanged_and_new_chapter_in_template(tmp_path):
    """The supplied nine-page XML stays exact while the next page gets a draft."""
    template = Path(r"C:/Users/LENOVO/Downloads/Udyam_Sutre_Sampurna_Granth_v19.docx")
    if not template.exists():
        pytest.skip("Author v19 template unavailable")
    chapter = {"number": 2, "title_mr": "उद्यमाची सुरुवात", "new_sutra": "उद्यमेन विवेकः॥",
               "padaccheda": "उद्यमेन विवेकः", "anvaya": "विवेकः उद्यमेन", "nirukta": "विवेक",
               "translation_mr": "उद्योगात विवेक", "derivation_mr": "सेतू", "explanation_mr": "उद्योग विवेक " * 250 + "\n\n" + "दुसरा विचार " * 250,
               "narada_sutra": {"text": "नारद", "brief_meaning_mr": "प्रेम"},
               "shandilya_sutra": {"text": "शांडिल्य", "brief_meaning_mr": "निष्ठा"},
               "examples": [{"kind": "positive", "person": "A", "business": "B", "description_mr": "उदाहरण", "source": "नोंद"},
                            {"kind": "cautionary", "person": "C", "business": "D", "description_mr": "सावधगिरी", "source": "नोंद"}],
               "dos_mr": ["कृती"], "donts_mr": ["टाळा"], "reflection_mr": "विचार", "reader_action_mr": "कार्य"}
    output = render_book(template, [chapter], tmp_path / "book.docx")
    with pytest.raises(ValueError, match="cannot enter Word book"):
        render_book(template, [{**chapter, "new_sutra": "कर्तव्यानपायेन विक्षेपहेतून् हित्वैकाधारे निष्ठा॥"}],
                    tmp_path / "long.docx")
    assert not (tmp_path / "long.docx").exists()
    assert not (tmp_path / "book.building.docx").exists()
    before, after = Document(template), Document(output)
    assert len(after.paragraphs) > 109
    assert all(before.paragraphs[i]._p.xml == after.paragraphs[i]._p.xml for i in range(109))
    assert "उद्यमेन विवेकः" in " ".join(p.text for p in after.paragraphs[109:])
    assert any(p.text == "उद्यम सूत्र २ : ॥ उद्यमेन विवेकः ॥" for p in after.paragraphs[109:])
    body = next(p for p in after.paragraphs[109:] if p.text.startswith("उद्योग विवेक"))
    assert body.runs[1].bold is False
    assert str(body.runs[1].font.color.rgb) == "1E1E1E"
    assert any(p.text.startswith("दुसरा विचार") for p in after.paragraphs[109:])
    assert any(p.text.startswith("निरुक्त : ") for p in after.paragraphs[109:])


def test_live_runner_one_new_chapter_with_fake_dispatch(tmp_path, monkeypatch):
    """The complete runner writes chapter two after an unchanged author prefix."""
    from types import SimpleNamespace
    from scripts import run_book_council_v19 as runner

    class Adapter:
        """Expose only the unchanged model identity to the runner."""
        def __init__(self, model_id):
            """Store the selected frozen model name."""
            self.model_id = model_id

    class Registry:
        """Return metadata without authenticating or calling a provider."""
        def __init__(self, offline_mode=False):
            """Accept the production constructor for the isolated test."""
        def get_adapter(self, role):
            """Resolve only the five expected role/model pairs."""
            return Adapter(next(model for configured, model in runner.MODELS.values() if configured == role))

    class Dispatch:
        """Answer stages with structured fixtures and capture all five roles."""
        calls = []
        def __init__(self, *args, **kwargs):
            """Accept budget settings while remaining offline."""
            self.calls, self.reserved_usd = [], 0.
        def call(self, role, prompt, system, **kwargs):
            """Produce one fixture chapter with 500 Marathi words."""
            payload = json.loads(prompt)
            stage = payload["stage"]
            self.calls.append((role, stage))
            if stage == "source_selection":
                answer = {"narada_id": "2", "shandilya_id": "2", "reason": "thematic fit"}
            elif stage == "challenge":
                speaker = payload["speaker"]
                answer = {"challenges": {peer: "Please cite the meaning" for peer in VOICES if peer != speaker}}
            elif stage == "reply":
                answer = {"answers": {peer: "Source text checked" for peer in VOICES
                                      if peer != payload["speaker"]}}
            elif stage == "proposal":
                answer = {"proposed_sutra": "उद्यमेन विवेकः", "derivation": "business focus"}
            elif stage.startswith("composition"):
                sources = payload["sources"]
                answer = {"title_mr": "अनन्यता", "new_sutra": "उद्यमेन विवेकः", "padaccheda": "उद्यमेन विवेकः",
                          "anvaya": "विवेकः उद्यमेन", "nirukta": "अर्थ", "translation_mr": "उद्यमाचा विवेक",
                          "derivation_mr": "मूळ तत्त्वातून आधुनिक उपयोग", "explanation_mr": "उद्योगात विवेक आवश्यक आहे " * 130,
                          "narada_sutra": {"text": sources["narada_sutra"]["text"], "brief_meaning_mr": "मूळ अर्थ"},
                          "shandilya_sutra": {"text": sources["shandilya_sutra"]["text"], "brief_meaning_mr": "मूळ अर्थ"},
                          "examples": [{"kind": "positive", "person": "Person A", "business": "Firm A", "description_mr": "उदाहरण", "source": "source"},
                                       {"kind": "cautionary", "person": "Person B", "business": "Firm B", "description_mr": "सावधगिरी", "source": "source"}],
                          "dos_mr": ["एक", "दोन", "तीन"], "donts_mr": ["एक", "दोन", "तीन"],
                          "reflection_mr": "चिंतन", "reader_action_mr": "आज कार्य करा"}
            elif stage.startswith("independent_review"):
                answer = {"verdict": "REVIEW_REQUIRED", "issues": ["Scholar to inspect Sanskrit"]}
            elif stage == "position" and role == "bharatiya_jnana_specialist":
                packet = payload["sources"]["registered_knowledge"]["passages"]
                answer = {"evidence": packet[0]["source_id"] if packet else "No matching registered passage"}
            else:
                answer = {"evidence": "source-led"}
            return SimpleNamespace(content=json.dumps(answer, ensure_ascii=False), was_truncated=False)

    monkeypatch.setattr(runner, "load_project_credentials", lambda folder: None)
    monkeypatch.setattr(runner, "ProviderRegistry", Registry)
    monkeypatch.setattr(runner, "BudgetedDispatcher", Dispatch)
    template = Path(r"C:/Users/LENOVO/Downloads/Udyam_Sutre_Sampurna_Granth_v19.docx")
    if not template.exists():
        pytest.skip("Author v19 template unavailable")
    result = runner.run_book(tmp_path, template, 2)
    assert result["chapters"] == 1
    assert len(Document(tmp_path / "Udyam_Sutre_v19_New_Book_DRAFT.docx").paragraphs) > 109
    report = json.loads((tmp_path / "report.json").read_text())
    assert len(report["chapters"]) == 1
    assert report["chapters"][0]["review"] == "REVIEW_REQUIRED"
    assert report["human_approval"] == "NOT_PERFORMED"
    from scripts.audit_book_v19 import audit_book
    audit = audit_book(tmp_path, template, 2)
    assert audit["status"] == "READY_FOR_AUTHOR_REVIEW"
    assert audit["validator_review_required"] == [2]

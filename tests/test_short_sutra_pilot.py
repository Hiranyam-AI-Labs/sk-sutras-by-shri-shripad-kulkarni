"""Offline safety checks for the single-chapter, capped short-sutra repair."""

import json

from scripts.pilot_short_sutra_v19 import (PILOT_LIMIT_USD, FIELDS,
                                           generate_pilot, plan)


def test_chapter_two_pilot_reuses_discussion_and_preserves_original(tmp_path):
    """A fake two-role repair writes a separate draft and reuses its checkpoint.

    The temporary folder holds synthetic council evidence. No provider,
    credential or actual author file is accessed. Inspect the saved candidate
    and call list when this regression fails.
    """
    from src.orchestration.book_council import VOICES

    source = {"narada_sutra": {"id": "10", "text": "नारद स्रोत"},
              "shandilya_sutra": {"id": "9", "text": "शांडिल्य स्रोत"}}
    draft = {"title_mr": "अनन्यता", "new_sutra": "कर्तव्यानपायेन विक्षेपहेतून् हित्वैकाधारे निष्ठा॥",
             "padaccheda": "जुना", "anvaya": "जुना", "nirukta": "जुना",
             "translation_mr": "जुना अर्थ", "derivation_mr": "जुना सेतू",
             "explanation_mr": "उद्योगात विवेक आवश्यक आहे " * 130,
             "narada_sutra": {"text": source["narada_sutra"]["text"], "brief_meaning_mr": "मूळ अर्थ"},
             "shandilya_sutra": {"text": source["shandilya_sutra"]["text"], "brief_meaning_mr": "मूळ अर्थ"},
             "examples": [{"kind": "positive", "person": "प्रथम व्यक्ति", "business": "प्रथम व्यवसाय",
                           "description_mr": "सावध कृती", "source": "नोंद"},
                          {"kind": "cautionary", "person": "द्वितीय व्यक्ति", "business": "द्वितीय व्यवसाय",
                           "description_mr": "चुकीची कृती", "source": "नोंद"}],
             "dos_mr": ["एक", "दोन", "तीन"], "donts_mr": ["एक", "दोन", "तीन"],
             "reflection_mr": "विचार", "reader_action_mr": "आज कार्य करा"}
    record = {"brief": {"number": 2, "reader_question": "पहिला आधार कोणता?"},
              "sources": source, "draft": draft,
              "discussion": {stage: {voice: {} for voice in VOICES}
                             for stage in ("position", "challenge", "reply")},
              "peer_review": {voice: {} for voice in VOICES[:-1]},
              "acceptance": {"independent_review": {"issues": ["जुने सूत्र मोठे आहे"]}}}
    (tmp_path / "chapter-02.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    calls = []

    def compose(request):
        """Return a compact replacement without changing source or cases."""
        calls.append("sutrakar")
        assert set(request["four_agent_discussion"]["reply"]) == set(VOICES)
        return {field: ("एकनिष्ठा उद्यमबलम्॥" if field == "new_sutra"
                        else "उद्योगात विवेक आवश्यक आहे " * 130 if field == "explanation_mr"
                        else "सुधारित मराठी अर्थ") for field in FIELDS}

    def validate(request):
        """Approve only the fake independent review for this offline test."""
        calls.append("validator")
        assert request["draft"]["examples"] == draft["examples"]
        return {"verdict": "PASS", "issues": []}

    def export(template, chapters, output):
        """Stand in for Word export and prove a separate candidate was selected."""
        assert chapters[0]["number"] == 2
        output.write_text("offline fixture", encoding="utf-8")
        return output

    summary = plan(tmp_path)
    assert summary["short_sutra_issues"] and summary["cap_usd"] == PILOT_LIMIT_USD == 1.0
    result = generate_pilot(tmp_path, tmp_path / "template.docx", compose, validate, export)
    assert result["draft"]["new_sutra"] == "एकनिष्ठा उद्यमबलम्॥"
    assert result["acceptance"]["status"] == "READY_FOR_SCHOLAR_REVIEW"
    assert result["human_approval"] == "NOT_PERFORMED"
    assert calls == ["sutrakar", "validator"]
    assert json.loads((tmp_path / "chapter-02.json").read_text(encoding="utf-8"))["draft"] == draft
    generate_pilot(tmp_path, tmp_path / "template.docx", compose, validate, export)
    assert calls == ["sutrakar", "validator"]

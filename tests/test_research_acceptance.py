"""Pure structural acceptance tests: no providers, credentials, network or DB."""

from copy import deepcopy
import unicodedata

import pytest

from src.orchestration.research_acceptance import assess_research_entry


@pytest.fixture
def sample():
    """Return synthetic canonical evidence and a structurally valid flat entry."""
    packet = {"references": [{
        "id": "western-1", "title": "Fixture source", "author": "Fixture author",
        "locator": "Chapter 1, paragraph 2", "original_text": "A supplied excerpt.",
        "meaning_mr": "स्रोताचा अर्थ", "url": "https://example.org/source",
        "tradition": "Western management",
    }], "examples": [{
        "case_id": f"case-{kind}", "kind": kind, "entity": f"Fixture {kind}",
        "text_mr": "पुरवलेला प्रसंग", "url": f"https://example.org/{kind}",
        "source_title": "Fixture case source",
    } for kind in ("positive", "caution")]}
    entry = {
        "id": "new-101", "number": 101, "chapter": 21, "title_mr": "विवेक",
        "new_sutra": "उद्यमेन विवेकः॥", "grammar_mr": "व्याकरण विश्लेषण",
        "translation_mr": "उद्योगात विवेक", "exposition": ["उद्योग " * 250, "विवेक " * 250],
        "references": ["western-1"],
        "comparative_mr": [{"source_id": "western-1", "explanation_mr": "स्रोताची तुलना"}],
        "examples": deepcopy(packet["examples"]),
        "dos_mr": ["विचार करा", "तपास करा", "कृती करा"],
        "donts_mr": ["घाई टाळा", "लोभ टाळा", "विलंब टाळा"],
        "application_mr": "व्यवसायात उपयोग", "action_mr": "आज तपासा", "summary_mr": "विवेक ठेवा",
    }
    return entry, packet


def assess(sample, prior=None, originals=None, used=None):
    """Evaluate fixtures with explicit empty histories by default."""
    return assess_research_entry(*sample, prior or [], originals or [], used or set())


def assert_issue(result, fragment):
    """Require a failed assessment with a diagnostic for the tested defect."""
    assert result["status"] == "NEEDS_REVISION"
    assert any(fragment in issue for issue in result["issues"]), result


def test_valid_western_only_entry_above_legacy_cap_and_no_mutation(sample):
    """No Narada/Shandilya pairing or old book cap is forced; inputs stay intact."""
    before = deepcopy(sample)
    prior, originals, used = ["अर्थेन कार्यम्"], ["सत्येन लाभः"], {"older-case"}
    histories = deepcopy((prior, originals, used))
    assert assess(sample, prior, originals, used) == {"status": "PASS", "issues": []}
    assert sample == before
    assert (prior, originals, used) == histories


@pytest.mark.parametrize("verse,fragment", [
    ("उद्यमेन", "two to four"), ("एक दोन तीन चार पाच", "two to four"),
    ("कर्तव्यानपायेन विक्षेपहेतून् हित्वैकाधारे निष्ठा॥", "32 characters"),
    ("उद्यमेन, विवेकः", "compound sentence"), ("business wisdom", "Devanagari"),
    ({"text": "उद्यमेन विवेकः"}, "new_sutra"),
])
def test_short_sutra_gate(sample, verse, fragment):
    """Use the shared shape gate and reject a non-flat or Latin formula."""
    sample[0]["new_sutra"] = verse
    assert_issue(assess(sample), fragment)


@pytest.mark.parametrize("history", ["prior", "originals"])
def test_normalized_duplicates_in_both_histories(sample, history):
    """Danda, punctuation and spacing cannot disguise an identical formula."""
    assert_issue(assess(sample, **{history: ["॥ उद्यमेन,\nविवेकः ।"]}), "duplicate formula")


def test_nfc_equivalence_and_distinct_nasals(sample):
    """Canonical equivalents match; chandrabindu and anusvara are not conflated."""
    sample[0]["new_sutra"] = "क़र्म उद्यमः"
    assert_issue(assess(sample, originals=[unicodedata.normalize("NFD", "क़र्म उद्यमः")]),
                 "forbidden_originals")
    sample[0]["new_sutra"] = "संयमः बलम्"
    assert assess(sample, originals=["सँयमः बलम्"])["status"] == "PASS"


@pytest.mark.parametrize("token", ["business", "123", "१२३", "उद्योगbusiness", "।", "ं"])
def test_non_devanagari_words_cannot_pad_exposition(sample, token):
    """Latin, numeric, mixed and punctuation-only tokens do not meet the quota."""
    sample[0]["exposition"] = ["उद्योग " * 499 + token + " " + token * 500]
    sample[0]["grammar_mr"] = "विवेक " * 600
    assert_issue(assess(sample), "499 Devanagari")


def test_exposition_exact_boundary_punctuation_and_joiners(sample):
    """Count only exposition, allowing ordinary punctuation and script shaping."""
    sample[0]["exposition"] = ["“उद्योग,” " * 499, "शक्\u200dती"]
    assert assess(sample)["status"] == "PASS"
    sample[0]["exposition"].pop()
    assert_issue(assess(sample), "499 Devanagari")


@pytest.mark.parametrize("field", ["id", "title_mr", "new_sutra", "grammar_mr",
                                    "translation_mr", "application_mr", "action_mr", "summary_mr"])
def test_required_text(sample, field):
    """Each required flat prose field must be nonblank."""
    sample[0][field] = " "
    assert_issue(assess(sample), field)


@pytest.mark.parametrize("field,value", [
    ("number", True), ("number", 0), ("number", "1"), ("chapter", []),
    ("chapter", False), ("exposition", "उद्योग " * 500), ("exposition", [None]),
    ("dos_mr", ["एक", "दोन"]), ("donts_mr", ["एक", "दोन", " "]),
])
def test_malformed_entry_fields_fail_closed(sample, field, value):
    """Wrong types/insufficient guidance produce issues rather than exceptions."""
    sample[0][field] = value
    assert_issue(assess(sample), field)


@pytest.mark.parametrize("field", ["original_text", "url", "locator", "title", "author",
                                    "meaning_mr", "tradition"])
def test_chosen_reference_requires_canonical_evidence(sample, field):
    """A source ID alone cannot stand in for supplied evidence."""
    sample[1]["references"][0][field] = ""
    assert_issue(assess(sample), field)


@pytest.mark.parametrize("url", ["source", "file:///private/source", "https://", "https://[bad",
                                  "https://example.org/with space"])
def test_source_url_must_be_structurally_valid(sample, url):
    """No remote fetch is needed to reject malformed/non-web provenance."""
    sample[1]["references"][0]["url"] = url
    assert_issue(assess(sample), "HTTP(S)")


def test_unknown_reference_and_missing_comparison(sample):
    """Every chosen ID must be supplied and individually compared."""
    sample[0]["references"].append("invented")
    result = assess(sample)
    assert_issue(result, "not in packet")
    assert_issue(result, "Missing comparison")


@pytest.mark.parametrize("comparisons,fragment", [
    ([], "Missing comparison"), (None, "comparative_mr"),
    ([{"source_id": "western-1", "explanation_mr": ""}], "explanation_mr"),
    ([{"source_id": "extra", "explanation_mr": "तुलना"}], "unchosen"),
    ([{"source_id": []}], "source_id"),
])
def test_comparison_contract(sample, comparisons, fragment):
    """Reject absent, malformed or extraneous per-source comparisons."""
    sample[0]["comparative_mr"] = comparisons
    assert_issue(assess(sample), fragment)


def test_duplicate_reference_and_comparison_ids(sample):
    """Duplicate records cannot masquerade as independent source coverage."""
    sample[0]["references"] *= 2
    sample[0]["comparative_mr"] *= 2
    sample[1]["references"] *= 2
    result = assess(sample)
    for fragment in ("Repeated reference", "Repeated comparison", "Duplicate packet references"):
        assert_issue(result, fragment)


@pytest.mark.parametrize("field", ["case_id", "kind", "entity", "text_mr", "url", "source_title"])
def test_case_fields_cannot_be_rewritten(sample, field):
    """Preserve every supplied identity, narrative, kind and citation exactly."""
    sample[0]["examples"][0][field] += " changed"
    assert_issue(assess(sample), "not in packet" if field == "case_id" else "changed canonical field")


def test_cases_must_be_exact_pair_and_globally_unused(sample):
    """Reject cross-entry reuse and local duplication even with unchanged text."""
    assert_issue(assess(sample, used={"case-positive"}), "already used")
    sample[0]["examples"][1] = deepcopy(sample[0]["examples"][0])
    result = assess(sample)
    assert_issue(result, "within entry")
    assert_issue(result, "match exactly")


@pytest.mark.parametrize("location", [0, 1])
def test_missing_or_extra_case_fails(sample, location):
    """Both canonical packet and generated entry must contain exactly two cases."""
    sample[location]["examples"].pop()
    assert_issue(assess(sample), "exactly")


def test_invalid_canonical_case_cannot_pass_by_matching_it(sample):
    """Exact equality cannot legitimize a malformed packet."""
    for container in sample:
        container["examples"][1]["kind"] = "positive"
        container["examples"][1]["url"] = "no URL"
    result = assess(sample)
    assert_issue(result, "one positive and one caution")
    assert_issue(result, "HTTP(S)")


@pytest.mark.parametrize("field", ["references", "examples"])
@pytest.mark.parametrize("value", [None, [], [None], [{"id": [], "case_id": []}]])
def test_malformed_collections_fail_closed(sample, field, value):
    """Untrusted lists and IDs must not trigger type errors."""
    sample[0][field] = deepcopy(value)
    sample[1][field] = deepcopy(value)
    assert assess(sample)["status"] == "NEEDS_REVISION"


@pytest.mark.parametrize("position,value", [(0, None), (1, []), (2, None), (3, [None]), (4, [])])
def test_invalid_top_level_inputs_fail_closed(sample, position, value):
    """History and packet containers are mandatory and must have declared types."""
    arguments = [*sample, [], [], set()]
    arguments[position] = value
    assert assess_research_entry(*arguments)["status"] == "NEEDS_REVISION"

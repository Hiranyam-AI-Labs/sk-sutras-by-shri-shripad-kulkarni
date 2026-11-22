"""Offline source-first prompt and foundation checks; no formulas or APIs."""
from copy import deepcopy

import pytest

from src.orchestration import source_first_writing as writing


# Return a small canonical packet with deliberately bulky internal provenance.
# All facts are synthetic; this fixture checks retention and minimization only.
def packet():
    return {'source_pair_ids': ['N1', 'S2'], 'pair_reference_ids': ['N1', 'S2'],
            'references': [{'id': identifier, 'original_text': 'परीक्षणासाठी मूळ पाठ'} for identifier in ('N1', 'S2', 'G3')],
            'examples': [{'case_id': 'C1', 'text_mr': 'कृत्रिम चाचणीतील अपरिवर्तित उदाहरण'}],
            'source_contexts': {'N1': {'sanskrit': 'मूळ पाठ', 'context_mr': 'मूळ अर्थाची मर्यादा',
                                      'source_note': 'पाठभेद जतन करावा'},
                                'G3': {'canonical_passage': 'संदर्भपाठ', 'context_mr': 'संदर्भ मर्यादा',
                                       'verification_record': {'bulky_internal': 'audit' * 1000},
                                       'source_record': {'meaning_limits_mr': 'व्यवसाय हा आधुनिक अर्थविस्तार आहे',
                                                         'private_audit': 'not model evidence'}}},
            'selection_provenance': {'selection_card': {'topic_mr': 'परीक्षण विषय'},
                'representative': {'research': {'source_core_mr': {'narada_mr': 'मूळ आशय'},
                                               'limitations_mr': 'प्रमाणित ग्रंथाचा दावा नाही'}}}}


# Verify source/case bytes and meaningful qualifications survive compaction,
# while unrelated internal proof bulk remains only in the canonical checkpoint.
def test_lean_packet_preserves_evidence_and_qualifications():
    original = packet()
    before = deepcopy(original)
    view = writing.lean_packet(original)
    assert original == before
    assert view['references'] == original['references']
    assert view['examples'] == original['examples']
    assert view['source_contexts']['N1']['source_note'] == 'पाठभेद जतन करावा'
    assert view['source_contexts']['G3']['source_qualifications']['meaning_limits_mr'] == 'व्यवसाय हा आधुनिक अर्थविस्तार आहे'
    assert 'verification_record' not in view['source_contexts']['G3']
    assert view['research_interpretation']['limitations_mr'] == 'प्रमाणित ग्रंथाचा दावा नाही'


# Verify both original sutras and actual supplementary support are prerequisites
# for a paid long composition, not optional citations added after the chapter.
@pytest.mark.parametrize('ids', [['N1', 'S2'], ['N1', 'G3'], ['S2', 'G3'], ['N1', 'S2', 'UNKNOWN']])
def test_missing_foundation_or_support_blocks_proposal(ids):
    with pytest.raises(ValueError):
        writing.require_proposal_support({'decision': 'ACCEPT', 'selected_source_ids': ids}, packet())


# Verify a fully sourced accepted proposal passes this cheap structural gate.
def test_full_source_proposal_support():
    writing.require_proposal_support({'decision': 'ACCEPT', 'selected_source_ids': ['N1', 'S2', 'G3']}, packet())


# Verify a composition that drops a foundational source cannot pass, even when
# the reused structural assessor has no other issues. No semantic truth claimed.
def test_composition_cannot_drop_canonical_source(monkeypatch):
    monkeypatch.setattr(writing, 'assess_research_entry', lambda *args: {'status': 'PASS', 'issues': []})
    entry = {'references': ['N1', 'G3'], 'comparative_mr': [{'source_id': 'N1'}, {'source_id': 'G3'}]}
    result = writing.assess_source_first_entry(entry, packet(), [], [], set())
    assert result['status'] == 'NEEDS_REVISION'
    assert len(result['issues']) == 2


# Verify malformed reference shapes return a held assessment instead of crashing
# after a model call; the original assessor still owns its normal schema checks.
def test_malformed_composition_reference_shape_is_held(monkeypatch):
    monkeypatch.setattr(writing, 'assess_research_entry', lambda *args: {'status': 'NEEDS_REVISION', 'issues': ['schema']})
    result = writing.assess_source_first_entry({'references': [{}], 'comparative_mr': None}, packet(), [], [], set())
    assert result['status'] == 'NEEDS_REVISION'


# Verify the source-first proposal contract expressly allows evidence-based
# rejection without a formula, avoiding forced writing and unnecessary fees.
def test_contract_allows_reject_and_keeps_source_priority():
    text = writing.writing_contract('proposal', {'scope': 'batch', 'entry_numbers': [1, 2]})
    assert "decision:'REJECT'" in text and 'NO proposed_sutra' in text
    assert 'BOTH source_pair_ids' in text

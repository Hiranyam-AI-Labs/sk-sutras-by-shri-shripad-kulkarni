"""Offline screening orchestration checks; synthetic evidence, no paid providers."""
from copy import deepcopy
import hashlib

import pytest

from src.orchestration.source_first_research import prepare_research_batch
from src.orchestration.source_first_stage import (
    compact_view, screen_batch, validate_evidence_review, resolve_component_ids,
)


# Return two synthetic primary pairs sharing one canonical passage. This fixture
# tests transport/bindings, not scholarship; every caller receives independent data.
def packet():
    hashes = {'narada': 'a' * 64, 'shandilya': 'b' * 64, 'test': 'c' * 64}
    candidates, evidence = [], []
    for number in (1, 2):
        source = {'id': number, 'sanskrit': 'परीक्षणार्थः पाठः',
                  'meaning_mr': 'हा मूळ सूत्रांचा दावा नसून परीक्षणासाठी तयार केलेला मजकूर आहे',
                  'context_mr': 'या उदाहरणातून वास्तविक ग्रंथाचे प्रमाणित विवेचन केलेले नाही'}
        candidates.append({'id': f'P{number}', 'narada': deepcopy(source),
                           'shandilya': deepcopy(source),
                           'source_hashes': {key: hashes[key] for key in ('narada', 'shandilya')},
                           'scores': {'meaning': 30, 'proposition': 12.5, 'context': 10, 'conditions': 7.5},
                           'total': 60, 'blockers': [], 'failed_primary_minima': []})
        text = 'हा केवळ स्वयंचलित चाचणीसाठी दिलेला एक कृत्रिम संदर्भ आहे'
        evidence.append({'id': f'E{number}', 'candidate_id': f'P{number}', 'source_id': 'test',
                         'source_sha256': hashes['test'], 'location': 'fixture 1',
                         'canonical_passage': text, 'passage_sha256': hashlib.sha256(text.encode()).hexdigest(),
                         'eligible': True, 'verified': True})
    return candidates, evidence, hashes


# Build a synthetic selection response for the exact fixture IDs. Returns model
# shaped prose, deliberately not any certification of the example source.
def selection():
    return {'assessments': [
        {'candidate_id': f'P{number}', 'status': 'SUPPORTED', 'evidence_ids': [f'E{number}'],
         'relation_kind': 'COMPLEMENTARY',
         'source_core_mr': {
             'narada_mr': 'पहिल्या परीक्षण मजकुरातील मुख्य विचार या स्वतंत्र वाक्यात नमूद केलेला आहे',
             'shandilya_mr': 'दुसऱ्या परीक्षण मजकुराचा स्वतंत्र आशय याच वाक्यात वेगळा स्पष्ट केला आहे'},
         'relation_mr': 'या कृत्रिम उदाहरणात दोन मजकुरांच्या संदर्भांचा संबंध तपासणीसाठी दर्शविला आहे',
         'limitations_mr': 'यातील परीक्षण परिणाम हा वास्तविक ग्रंथाच्या तत्त्वज्ञानाचा अधिकृत निष्कर्ष समजता येणार नाही',
         'business_extension_mr': 'कामातील उद्देश स्पष्ट ठेवण्याचा स्वतंत्र आधुनिक उपयोग उदाहरण म्हणून सुचविला आहे'}
        for number in (1, 2)]}


# Verify token reduction does not remove canonical text or cross pair-ID menus.
def test_compaction_deduplicates_passage_without_losing_pair_binding():
    candidates, evidence, hashes = packet()
    candidates[0]['narada']['source_note'] = 'पाठभेदाची ही अट जतन करावी'
    request = prepare_research_batch('test', candidates, evidence, hashes)
    before = deepcopy(request)
    view = compact_view(request)
    assert len(view['reference_library']) == 1
    assert [row['evidence_menu'][0]['evidence_id'] for row in view['candidates']] == ['E1', 'E2']
    assert view['reference_library'][0]['canonical_passage'] == evidence[0]['canonical_passage']
    assert view['candidates'][0]['narada']['source_note'] == candidates[0]['narada']['source_note']
    assert request == before


# Verify an independent review hold quarantines a pair despite researcher support.
def test_supported_pair_does_not_advance_when_validator_holds(tmp_path):
    calls = []

    def provider(voice, stage, system, payload, tokens):
        """Return deterministic fake model replies and record role ordering."""
        calls.append(voice)
        if voice == 'researcher':
            return selection()
        assert 'selected_evidence' in payload['assessments'][0]
        return {'decisions': [{'candidate_id': 'P1', 'verdict': 'PASS', 'issues_mr': []},
                              {'candidate_id': 'P2', 'verdict': 'REVIEW_REQUIRED',
                               'issues_mr': ['संबंधाची मर्यादा स्पष्ट नाही']} ]}

    result = screen_batch('test', *packet(), provider, tmp_path)
    assert calls == ['researcher', 'validator']
    assert result['supported_and_reviewed'] == ['P1']
    assert result['held_for_review'] == ['P2']
    assert result['new_sutras'] == 0


# Verify unknown regenerated fields stop before a second paid-style callback.
def test_generated_quote_stops_before_independent_call(tmp_path):
    calls = []

    def provider(voice, *args):
        """Supply an invalid new quote field; no live provider is constructed."""
        calls.append(voice)
        answer = selection()
        answer['assessments'][0]['quote'] = 'invented'
        return answer

    with pytest.raises(ValueError):
        screen_batch('test', *packet(), provider, tmp_path)
    assert calls == ['researcher']


# Verify missing, duplicated and inconsistent independent verdicts fail closed.
@pytest.mark.parametrize('decisions', [[],
    [{'candidate_id': 'P1', 'verdict': 'PASS', 'issues_mr': []}] * 2,
    [{'candidate_id': 'P1', 'verdict': 'PASS', 'issues_mr': ['defect']},
     {'candidate_id': 'P2', 'verdict': 'PASS', 'issues_mr': []}],
])
def test_review_coverage_and_consistency(decisions):
    with pytest.raises(ValueError):
        validate_evidence_review(['P1', 'P2'], {'decisions': decisions})


# Return synthetic proof that verse 12.14 is literally inside one canonical
# combined record. It is only an ID-resolution fixture, not an actual verse.
def component_packet():
    text = 'कृत्रिम एक\nकृत्रिम दोन'
    part = 'कृत्रिम दोन'
    source = {'original_passage': text, 'passage_sha256': hashlib.sha256(text.encode()).hexdigest(),
              'components': [{'locator': '12.14', 'original_passage': part,
                              'passage_sha256': hashlib.sha256(part.encode()).hexdigest(),
                              'attestation_status': 'ATTESTED_PRIMARY_ONLINE_TEXT'}]}
    evidence = {'id': 'P1::DEV-GITA-12-13-14', 'candidate_id': 'P1',
                'source_id': 'DEV-GITA-12-13-14', 'verified': True, 'eligible': True,
                'canonical_passage': text, 'passage_sha256': source['passage_sha256'],
                'source_record': source}
    raw = {'assessments': [{'candidate_id': 'P1', 'evidence_ids': ['P1::DEV-GITA-12-14']}]}
    return {'evidence_records': [evidence]}, raw


# Verify a narrower attested verse is resolved without a new quote/model call,
# while the raw saved model response stays unchanged and the mapping is audited.
def test_attested_component_maps_only_to_existing_parent():
    request, raw = component_packet()
    before = deepcopy(raw)
    normalized, ledger = resolve_component_ids(request, raw)
    assert raw == before
    assert normalized['assessments'][0]['evidence_ids'] == ['P1::DEV-GITA-12-13-14']
    assert ledger[0]['attested_component_locator'] == '12.14'


# Verify aliases do not permit invented, cross-pair, unverified or ambiguous
# citations. Every such case must fail before an independent paid callback.
@pytest.mark.parametrize('kind', ['invented', 'cross_pair', 'unverified', 'ambiguous', 'not_contained'])
def test_component_resolution_fails_closed(kind):
    request, raw = component_packet()
    if kind == 'invented':
        raw['assessments'][0]['evidence_ids'] = ['P1::DEV-GITA-12-15']
    elif kind == 'cross_pair':
        raw['assessments'][0]['candidate_id'] = 'P2'
    elif kind == 'unverified':
        request['evidence_records'][0]['verified'] = False
    elif kind == 'ambiguous':
        other = deepcopy(request['evidence_records'][0])
        other['id'] = 'P1::DEV-GITA-12-12-14'
        request['evidence_records'].append(other)
    else:
        component = request['evidence_records'][0]['source_record']['components'][0]
        component['original_passage'] = 'वेगळा पाठ'
        component['passage_sha256'] = hashlib.sha256(component['original_passage'].encode()).hexdigest()
    with pytest.raises(ValueError):
        resolve_component_ids(request, raw)

"""Offline input/CLI boundaries; no customer API adapters are constructed."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from scripts import run_source_first_research as runner


# Write one synthetic attested supplemental reference with exact file binding.
# Returns its canonical record; tests intentionally do not certify a real source.
def library_fixture(path):
    text = 'केवळ चाचणीसाठी कृत्रिम संदर्भ'
    record = {'id': 'TEST', 'reuse_status': 'QUALIFIED_RESEARCH_READY', 'blockers': [],
              'original_passage': text, 'locator': 'fixture 1',
              'passage_sha256': hashlib.sha256(text.encode()).hexdigest(),
              'work': 'Synthetic fixture', 'faithful_meaning_mr': 'परीक्षणासाठी अर्थ',
              'meaning_qualifications_mr': 'वास्तविक प्राचीन ग्रंथ नाही'}
    corpus = json.dumps({'passages': [record]}, ensure_ascii=False).encode()
    (path / 'evidence-corpus.json').write_bytes(corpus)
    audit = {'gate': 'PASS_WITH_LIMITS',
             'reviewed_corpus': {'sha256': hashlib.sha256(corpus).hexdigest()}}
    (path / 'evidence-corpus-independent-review.json').write_text(json.dumps(audit))
    check = {'record_id': 'TEST', 'status': 'MATCH', 'eligible_for_small_calibration': True,
             'narada_shandilya_repeat': False, 'existing_quote': text,
             'existing_locator': record['locator'], 'existing_passage_sha256': record['passage_sha256']}
    (path / 'evidence-primary-verification.json').write_text(
        json.dumps({'records': [check], 'eligible_calibration_record_ids': ['TEST']}, ensure_ascii=False),
        encoding='utf-8')
    return record


# Verify exact attestation enables a canonical reference without rewriting text.
def test_attested_library_preserves_literal_text(tmp_path):
    record = library_fixture(tmp_path)
    library, hashes = runner.verified_library(tmp_path)
    assert len(library) == 1 and library[0]['verified'] is True
    assert library[0]['canonical_passage'] == record['original_passage']
    assert library[0]['source_sha256'] == hashes['evidence_corpus']


# Verify stale corpus reviews and materially mismatched quotations stop selection.
@pytest.mark.parametrize('kind', ['stale_review', 'changed_quote', 'variant', 'circular_support'])
def test_unverified_or_changed_library_rejected(tmp_path, kind):
    library_fixture(tmp_path)
    if kind == 'stale_review':
        path = tmp_path / 'evidence-corpus.json'
        path.write_bytes(path.read_bytes() + b' ')
    else:
        path = tmp_path / 'evidence-primary-verification.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        row = data['records'][0]
        if kind == 'changed_quote':
            row['existing_quote'] += ' बदल'
        elif kind == 'variant':
            row['status'] = 'VARIANT'
        else:
            row['narada_shandilya_repeat'] = True
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    with pytest.raises(ValueError):
        runner.verified_library(tmp_path)


# Verify a shared source keeps distinct pair-specific evidence IDs and exact text.
def test_pair_evidence_does_not_merge_or_mutate_inputs():
    candidates = [{'id': 'N1-S1'}, {'id': 'N1-S2'}]
    library = [{'source_id': 'G1', 'canonical_passage': 'मूळ पाठ'}]
    before = deepcopy((candidates, library))
    records = runner.pair_evidence(candidates, library)
    assert [row['id'] for row in records] == ['N1-S1::G1', 'N1-S2::G1']
    assert [row['candidate_id'] for row in records] == ['N1-S1', 'N1-S2']
    assert (candidates, library) == before


# Verify default preparation cannot load credentials or make provider calls.
def test_dry_run_never_constructs_provider(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        """Fail if any test attempts to construct the explicit live boundary."""
        raise AssertionError('Live setup forbidden')
    monkeypatch.setattr(runner, 'create_live_provider', forbidden)
    result = runner.run({'candidate_count': 243, 'reference_count': 11}, tmp_path)
    assert result['paid_calls'] == 0 and result['status'] == 'OFFLINE_PREPARED'


# Verify a stale declared candidate count is rejected before any normalization.
def test_primary_declared_count_cannot_hide_missing_candidates():
    with pytest.raises(ValueError):
        runner.primary_inputs({'manifest_role': 'PRIMARY_ONLY', 'candidate_count': 243, 'candidates': []})


# Verify extending the returned global registry cannot mutate any pair's narrow
# two-source hash binding, including the final input record after score sorting.
def test_primary_registry_is_not_aliased_to_last_candidate():
    records = []
    for index in range(243):
        records.append({'pair_id': f'P{index}',
            'sources': {name: {'file_sha256': ('a' if name == 'narada' else 'b') * 64,
                               'record': {'id': index + 1}} for name in ('narada', 'shandilya')},
            'assessment': {'scores': {}, 'total': index, 'blockers': []},
            'failed_primary_component_minima': []})
    rows, registry = runner.primary_inputs({'manifest_role': 'PRIMARY_ONLY', 'candidate_count': 243,
                                            'candidates': records})
    registry['external'] = 'c' * 64
    assert all(set(row['source_hashes']) == {'narada', 'shandilya'} for row in rows)


# Verify fresh devotional evidence cannot bypass its independent interpretation
# hold. All text and attestation labels here are synthetic offline fixtures.
def test_devotional_hold_excluded_and_review_hash_bound(tmp_path):
    records = []
    for identifier in ('D1', 'D2'):
        text = f'कृत्रिम परीक्षण {identifier}'
        records.append({'id': identifier, 'blockers': [],
            'attestation_status': 'ATTESTED_PRIMARY_ONLINE_TEXT',
            'original_passage': text, 'passage_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'locator': 'fixture', 'work': 'Synthetic test', 'faithful_meaning_mr': 'कृत्रिम अर्थ',
            'context_mr': 'परीक्षण संदर्भ', 'meaning_limits_mr': 'प्रमाणित ग्रंथ नाही'})
    data = json.dumps({'records': records}, ensure_ascii=False).encode()
    (tmp_path / 'evidence-devotional-supplement.json').write_bytes(data)
    review = {'gate': 'PASS_WITH_LIMITS', 'reviewed_file': {'sha256': hashlib.sha256(data).hexdigest()},
              'unresolved_required_corrections': [],
              'per_record': [{'id': 'D1', 'disposition': 'USABLE'}, {'id': 'D2', 'disposition': 'HOLD'}]}
    path = tmp_path / 'evidence-devotional-independent-review.json'
    path.write_text(json.dumps(review))
    library, hashes = runner.devotional_library(tmp_path)
    assert [row['source_id'] for row in library] == ['D1']
    assert library[0]['source_sha256'] == hashes['devotional_supplement']
    review['reviewed_file']['sha256'] = '0' * 64
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError):
        runner.devotional_library(tmp_path)


# Verify the paid-style runner actually applies the tested established timeout
# before invoking a batch. Both factory and screener are fake; no SDK is loaded.
def test_live_style_run_sets_established_timeouts_before_screening(tmp_path, monkeypatch):
    adapters = {name: SimpleNamespace(timeout_seconds=60., effort=None)
                for name in ('narada', 'shandilya', 'researcher', 'sutrakar', 'validator')}
    client = SimpleNamespace(adapters=adapters,
                             dispatcher=SimpleNamespace(calls=0, reserved_usd=0.))
    monkeypatch.setattr(runner, 'create_live_provider', lambda *args, **kwargs: client)

    def screen(*args, **kwargs):
        """Assert timeout correction before returning a synthetic accepted gate."""
        assert all(adapter.timeout_seconds == 240. for adapter in adapters.values())
        return {'supported_and_reviewed': ['P1']}

    monkeypatch.setattr(runner, 'screen_batch', screen)
    plan = {'candidate_count': 1, 'reference_count': 0, 'source_hashes': {},
            'candidates': [{'id': 'P1'}], 'library': [], 'batches': [['P1']], 'plan_sha256': 'test'}
    report = runner.run(plan, tmp_path, live=True)
    assert report['status'] == 'CALIBRATION_SCREENED'
    assert adapters['researcher'].effort == 'low'


# Verify a pending recovery cannot even load credentials or construct adapters,
# despite explicit live/resume flags. Independent review is a pre-call gate.
def test_pending_timeout_recovery_stops_before_provider_setup(tmp_path, monkeypatch):
    review = {'gate': 'PASS', 'unresolved_required_corrections': []}
    data = json.dumps(review).encode()
    (tmp_path / 'timeout-recovery-independent-review.json').write_bytes(data)
    diagnostic = {'status': 'OFFLINE_VERIFIED_CONFIGURATION_CORRECTION',
                  'independent_review_status': 'PENDING',
                  'independent_review_sha256': hashlib.sha256(data).hexdigest()}
    (tmp_path / 'timeout-correction-diagnostic.json').write_text(json.dumps(diagnostic))

    def forbidden(*args, **kwargs):
        """Tripwire: unreviewed correction cannot construct a paid client."""
        raise AssertionError('Provider setup forbidden')

    monkeypatch.setattr(runner, 'create_live_provider', forbidden)
    with pytest.raises(ValueError, match='independently passed'):
        runner.run({}, tmp_path, live=True, resume=True, recover_timeout=True)

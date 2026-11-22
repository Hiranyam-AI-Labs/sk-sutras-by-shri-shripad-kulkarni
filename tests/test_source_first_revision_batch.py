"""Offline grouped-HOLD boundary/integration tests; synthetic facts and fake models."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import run_source_first_revision_batch as batch
from scripts import run_source_first_selected_book as selected
from tests.test_source_first_revision_runner import revision_options, snapshot
from tests.test_source_first_book_runner import Registry
from tests.test_source_first_case_capsule import build_case_capsule, case_work, apply_case_capsule
from src.orchestration.research_council import ResearchCouncil


class GroupRegistry(Registry):
    """Use all five fixed fake adapters; allow just repair and three peer stages."""

    def __init__(self, reject=(), hold=(), missing=False, missing_issue=False, bad_quote=False, failure=False):
        """Configure deterministic mixed dispositions and terminal malformed responses."""
        super().__init__(); self.reject, self.hold = set(reject), set(hold)
        self.missing, self.missing_issue, self.bad_quote, self.failure = missing, missing_issue, bad_quote, failure

    def generate(self, voice, adapter, prompt, system):
        """Observe actual SDK-bound thinking controls, retaining the standard fake dispatch."""
        if voice == 'narada':
            assert adapter.thinking_level == 'MEDIUM'
        response = super().generate(voice, adapter, prompt, system)
        self.calls[-1]['thinking_level'] = getattr(adapter, 'thinking_level', None)
        return response

    def respond(self, voice, payload):
        """Check selected-only prompt coverage and return current-proposal decisions."""
        assert payload['stage'] in ('proposal', 'peer_review')
        assert voice != 'validator'
        numbers = payload['entry_numbers']; keys = {str(n) for n in numbers}
        assert set(payload['sources']) == keys
        assert set(payload['original_proposals']) == keys
        assert {b['number'] for b in payload['briefs']} == set(numbers)
        assert set(payload['discussion']) == {'position', 'challenge', 'reply'}
        for stage, field in (('position', 'positions'), ('challenge', 'challenges'), ('reply', 'answers')):
            assert set(payload['discussion'][stage]) == set(batch.r.VOICES)
            for row in payload['discussion'][stage].values():
                maps = [row[field]] if stage == 'position' else row[field].values()
                assert all(set(m) == keys for m in maps)
        if self.failure:
            raise TimeoutError('Synthetic grouped provider failure')
        if payload['stage'] == 'proposal':
            assert voice == 'sutrakar'
            proposals = []
            for n in numbers:
                if n in self.reject:
                    proposal = {'number': n, 'decision': 'REJECT',
                        'rejection_reason': 'कृत्रिम चाचणीतील मर्यादित संबंध अपुरा असल्याने हा प्रस्ताव नाकारला आहे'}
                else:
                    proposal = deepcopy(payload['original_proposals'][str(n)])
                    proposal.update(proposed_sutra={2: 'प्रमाणेन निर्णयः', 3: 'निष्ठया सेवा'}[n],
                        derivation=f'Revised existing-source relationship for synthetic candidate {n}',
                        business_action_mr=f'चाचणी कृती ठराविक परिस्थितीत प्रत्यक्ष करून पाहणे सुधारित मर्यादा {n}')
                proposals.append(proposal)
            if self.missing:
                proposals.pop()
            responses = [{'issue_id': i['issue_id'], 'disposition': 'CONTESTED',
                          'reason_mr': 'कृत्रिम चाचणीत स्रोत संबंध आणि मर्यादा स्पष्ट केल्या आहेत'}
                         for i in payload['original_peer_issues']]
            if self.missing_issue:
                responses.pop()
            return {'proposals': proposals, 'revision_responses': responses}
        rows = []
        for p in payload['proposal']['proposals']:
            n = p['number']; row = {'number': n, 'verdict': 'PASS', 'issues': []}
            assert payload['current_formula_shapes'][str(n)] == batch.r.formula_shape(p)
            if voice == 'researcher' and (n in self.hold or self.bad_quote):
                row.update(verdict='REVIEW_REQUIRED', issues=[{'field': 'derivation',
                    'quote': 'Synthetic test derivation only' if self.bad_quote else p['derivation'],
                    'reason': 'Synthetic current-proposal scope remains unresolved', 'severity': 'medium'}])
            rows.append(row)
        return {'reviews': rows}


@pytest.fixture(autouse=True)
def no_live(monkeypatch):
    """Trip before credential loaders or live adapters can be constructed."""
    def blocked(*args, **kwargs):
        """Reject every attempted nonfake registry or live dispatch setup."""
        pytest.fail('Real credentials and paid providers forbidden')
    monkeypatch.setattr(batch.r, 'create_live_provider', blocked)
    monkeypatch.setattr('scripts.run_research_book.load_project_credentials', blocked)
    monkeypatch.setattr('src.providers.registry.ProviderRegistry', blocked)


@pytest.fixture
def options(tmp_path, monkeypatch):
    """Build a real original ten-entry saved batch with multiple synthetic HOLDs."""
    original = revision_options(tmp_path, monkeypatch, number=2, original_target=2)
    original.pop('number'); original.pop('candidate_sha256')
    original['numbers'] = [2, 3]
    original['candidate_sha256'] = {str(n): batch.r.byte_hash(original['source_dir'] / f'candidate-{n:03d}.json')
                                  for n in original['numbers']}
    original['work'] = tmp_path / 'br'
    gate = tmp_path / 'batch-gate.json'
    batch.r.save(gate, {'status': 'PASS', 'paid_calls': 0, 'code_sha256': batch.code_bindings(),
        'tests': [{'path': batch.TEST, 'passed': 1, 'failed': 0, 'errors': 0}]})
    original['batch_gate'] = gate

    def no_rounds(*args, **kwargs):
        """Catch even one repeated position/challenge/reply round after fixture setup."""
        pytest.fail('Original completed discussion must never run again')
    monkeypatch.setattr(ResearchCouncil, 'run_batch_discussion', no_rounds)
    return original


def test_group_four_calls_full_journal_untouched_siblings_capsules_and_resume(options, tmp_path):
    """Two real HOLDs share four fake calls; existing consumers need no changes."""
    before = snapshot(options['source_dir']); fake = GroupRegistry()
    c0 = batch.r.load(options['source_dir'] / 'candidate-002.json')
    name = c0['discussion_file']; old = batch.r.load(options['source_dir'] / name)
    report = batch.run(**options, registry=fake)
    assert report['status'] == 'COMPLETED' and report['new_calls'] == 4
    assert [c['voice'] for c in fake.calls] == ['sutrakar', 'narada', 'shandilya', 'researcher']
    assert report['composition_calls'] == report['validator_calls'] == 0
    for call in fake.calls:
        assert call['timeout'] == 240
        assert call['tokens'] == (16384 if call['voice'] == 'narada' else 5000)
        if batch.r.selection.PROVIDERS[call['voice']] == 'anthropic':
            assert call['effort'] == 'medium'
        elif call['voice'] == 'narada':
            assert call['effort'] == 'original' and call['thinking_level'] == 'MEDIUM'
    derived = batch.r.load(options['work'] / name)
    assert derived['discussion'] == old['discussion']
    assert [p for p in derived['proposal']['proposals'] if p['number'] not in (2, 3)] == [
        p for p in old['proposal']['proposals'] if p['number'] not in (2, 3)]
    for v in batch.r.VOICES[:-1]:
        assert [p for p in derived['peer_review'][v]['reviews'] if p['number'] not in (2, 3)] == [
            p for p in old['peer_review'][v]['reviews'] if p['number'] not in (2, 3)]
    input_name = name.replace('-discussion.json', '-input.json')
    assert (options['work'] / input_name).read_bytes() == (options['source_dir'] / input_name).read_bytes()
    provenance = batch.r.load(options['work'] / 'revision-provenance.json')
    assert provenance['original_proposals']['2'] == c0['proposal']
    assert provenance['original_peer_reviews']['2']['researcher']['verdict'] == 'REVIEW_REQUIRED'
    assert {i['number'] for i in provenance['original_issues']} == {2, 3}
    assert len({i['issue_id'] for i in provenance['original_issues']}) == len(provenance['original_issues'])
    assert len(provenance['provider_calls']) == 4
    for proof in provenance['provider_calls']:
        assert batch.r.byte_hash(options['work'] / proof['request_document']['path']) == proof['request_document']['sha256']
        request = batch.r.load(options['work'] / proof['request_document']['path'])
        actual_call = next(c for c in fake.calls if c['voice'] == proof['voice'])
        assert proof['max_output_tokens'] == request['max_output_tokens'] == actual_call['tokens']
        assert proof['generation_options'] == request['generation_options'] == (
            {'thinking_level': 'MEDIUM'} if proof['voice'] == 'narada' else {})
        assert batch.r.byte_hash(options['work'] / 'provider' / 'raw' / (proof['slot'] + '.txt')) == proof['raw_response_sha256']
    pool = case_work(tmp_path / 'proofs'); supplied = batch.r.load(options['work'] / input_name)
    used, identity = set(), set()
    for n, pair in ((2, ('positive-a', 'caution-b')), (3, ('positive-c', 'caution-d'))):
        candidate_path = options['work'] / f'candidate-{n:03d}.json'
        candidate = batch.r.load(candidate_path)
        assert candidate['status'] == 'ACCEPTED_FOR_CASE_ASSIGNMENT'
        assert all(p['verdict'] == 'PASS' and not p['issues'] for p in candidate['peer_review'].values())
        brief = next(b for b in supplied['briefs'] if b['number'] == n); sources = supplied['source_packets'][str(n)]
        capsule = build_case_capsule(number=n, brief=brief, sources=sources,
            discussion=derived['discussion'], proposal=derived['proposal'], peer_review=derived['peer_review'],
            case_work_dir=pool, used_case_ids=used, used_identity_keys=identity,
            case_slots=[{'kind': kind, 'case_id': ident, 'fit_reason_mr': 'कृत्रिम चाचणीतील स्पष्ट मर्यादित उपयोग',
                         'limitations_mr': 'ही ऐतिहासिक सत्यता प्रमाणित करणारी चाचणी नाही'}
                        for kind, ident in zip(('positive', 'caution'), pair)])
        task = {'number': n, 'brief': brief, 'source_packet': sources, 'case_capsule': capsule}
        for key, path in (('selection_input', options['work'] / input_name),
                          ('selection_discussion', options['work'] / name), ('candidate_record', candidate_path)):
            task[key] = {'path': str(path), 'sha256': batch.r.byte_hash(path)}
        assert selected.validate_task(task, tmp_path, used, identity)['proposal'] == candidate['proposal']
        effective, _ = apply_case_capsule(capsule, number=n, brief=brief, sources=sources,
            discussion=derived['discussion'], proposal=derived['proposal'], peer_review=derived['peer_review'], used_case_ids=used)
        for assignment in effective['case_assignments']:
            used.add(assignment['case_id']); identity.update(assignment['identity_reservations'])
    saved = (options['work'] / 'result.json').read_bytes()
    assert batch.run(**options, registry=fake, resume=True)['new_calls'] == 0
    assert len(fake.calls) == 4 and (options['work'] / 'result.json').read_bytes() == saved
    assert snapshot(options['source_dir']) == before


def test_mixed_reject_and_still_held_do_not_become_case_ready(options):
    """One rejection and one unresolved fresh peer issue remain distinct nonadvancing outcomes."""
    fake = GroupRegistry(reject=(2,), hold=(3,)); result = batch.run(**options, registry=fake)
    assert [c['status'] for c in result['candidates']] == ['REJECTED', 'HOLD_PEER_REVIEW']
    for row in result['candidates']:
        candidate = batch.r.load(options['work'] / row['path'])
        assert candidate['case_curation_eligible'] is False
        if row['number'] == 2:
            assert 'proposed_sutra' not in candidate['proposal']
    assert len(fake.calls) == 4
    assert batch.run(**options, registry=fake, resume=True)['new_calls'] == 0


@pytest.mark.parametrize('fault', ['missing', 'missing_issue', 'bad_quote', 'failure'])
def test_bad_coverage_feedback_or_provider_failure_is_terminal_without_retry(options, fault):
    """Malformed groups, old quotes and SDK failure retain charges and cannot start a chain."""
    fake = GroupRegistry(**{fault: True})
    with pytest.raises(batch.r.SourceFirstStopped):
        batch.run(**options, registry=fake)
    count = len(fake.calls)
    assert count == (4 if fault == 'bad_quote' else 1)
    assert batch.r.load(options['work'] / 'report.json')['reservation_usd'] > 0
    with pytest.raises(batch.r.SourceFirstStopped):
        batch.run(**options, registry=fake, resume=True)
    assert len(fake.calls) == count


@pytest.mark.parametrize('fault', ['different_batch', 'candidate', 'input', 'discussion', 'batch_gate', 'base_gate'])
def test_original_group_drift_and_gates_fail_before_keys(options, fault):
    """No live factory runs for cross-batch HOLDs, drift or either stale receipt."""
    if fault == 'different_batch':
        options['numbers'] = [1, 2]
        options['candidate_sha256'] = {str(n): batch.r.byte_hash(options['source_dir'] / f'candidate-{n:03d}.json') for n in (1, 2)}
    elif fault == 'candidate':
        options['candidate_sha256']['3'] = '0' * 64
    elif fault in ('input', 'discussion'):
        options[fault + '_sha256'] = '0' * 64
    else:
        gate_path = options['batch_gate' if fault == 'batch_gate' else 'offline_gate']
        gate = batch.r.load(gate_path); gate['code_sha256'] = {}; batch.r.save(gate_path, gate)
    with pytest.raises(ValueError):
        batch.run(**options, live=True, credentials_dir='must-not-load')
    assert not options['work'].exists()


@pytest.mark.parametrize('numbers', [[2, 2], [3, 2], [], [2, 3, 4, 5, 6, 7], [True]])
def test_group_bound_and_coverage_are_explicit(options, numbers):
    """Never discover, reorder, duplicate or silently split a caller's selected group."""
    with pytest.raises(ValueError):
        batch.run(**{**options, 'numbers': numbers})
    assert not options['work'].exists()


def test_preflight_is_read_only(options):
    """No fake injection/live opt-in means no work creation or adapter construction."""
    assert batch.run(**options)['status'] == 'OFFLINE_PREFLIGHT_PASS'
    assert not options['work'].exists()


@pytest.mark.parametrize('numbers,tokens', [([2], 4096), ([2, 3, 4, 5, 6], 12500)])
def test_actual_singleton_and_maximum_group_token_caps(options, numbers, tokens):
    """Actual singleton/five-entry Gemini calls keep thinking headroom; others scale."""
    options['numbers'] = numbers
    options['candidate_sha256'] = {str(n): batch.r.byte_hash(options['source_dir'] / f'candidate-{n:03d}.json') for n in numbers}
    fake = GroupRegistry(reject=(4, 5, 6)); result = batch.run(**options, registry=fake)
    assert result['status'] == 'COMPLETED' and len(fake.calls) == 4
    assert all(call['tokens'] == (16384 if call['voice'] == 'narada' else tokens)
               and call['timeout'] == 240 for call in fake.calls)
    proofs = batch.r.load(options['work'] / 'revision-provenance.json')['provider_calls']
    assert {p['voice']: p['max_output_tokens'] for p in proofs} == {c['voice']: c['tokens'] for c in fake.calls}


def test_receipt_refresh_is_separate_but_comparator_drift_stops_resume(options, tmp_path):
    """Exact eligible committed results inform all four paid prompts, not new source claims."""
    from tests.test_source_first_book_export import ready
    committed = ready(1, 'opening')
    committed['proposal'].update(business_decision_mr='कृत्रिम आधीचा व्यवसायनिर्णय', business_action_mr='कृत्रिम आधीची प्रत्यक्ष कृती')
    path = tmp_path / 'committed.json'; batch.r.save(path, committed)
    options['committed_results'] = [{'path': str(path), 'sha256': batch.r.byte_hash(path)}]
    fake = GroupRegistry(); batch.run(**options, registry=fake)
    for call in fake.calls:
        view = json.loads(call['prompt'])['input']
        assert view['committed_decisions'][0]['business_action_mr'] == committed['proposal']['business_action_mr']
        assert committed['draft']['new_sutra'] in view['prior_formulas']
    gate = batch.r.load(options['batch_gate']); gate['tests'][0]['passed'] += 1; batch.r.save(options['batch_gate'], gate)
    assert batch.run(**options, registry=fake, resume=True)['new_calls'] == 0
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError):
        batch.run(**options, registry=fake, resume=True)
    assert len(fake.calls) == 4


def test_unready_or_wrong_hash_committed_result_stops_before_keys(options, tmp_path):
    """Pending, stale or malformed book evidence cannot masquerade as committed comparators."""
    path = tmp_path / 'not-ready.json'; batch.r.save(path, {'status': 'PENDING'})
    options['committed_results'] = [{'path': str(path), 'sha256': batch.r.byte_hash(path)}]
    with pytest.raises(ValueError):
        batch.run(**options, live=True, credentials_dir='must-not-load')
    options['committed_results'][0]['sha256'] = '0' * 64
    with pytest.raises(ValueError):
        batch.run(**options, live=True, credentials_dir='must-not-load')
    assert not options['work'].exists()

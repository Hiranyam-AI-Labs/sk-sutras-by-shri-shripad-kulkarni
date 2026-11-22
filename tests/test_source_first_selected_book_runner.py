"""Fake-only composition wiring; real saved selection/capsule/council/reviewer APIs.

All cases are synthetic structural fixtures. No credential, SDK, paid call,
historical assertion, production checkpoint or publication is permitted.
"""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest

from scripts import run_source_first_selected_book as runner
from scripts import run_source_first_selection as selector
from src.orchestration.source_first_case_capsule import build_case_capsule, apply_case_capsule
from src.orchestration.research_council import ResearchCouncil
from tests.test_source_first_selection_runner import options as selection_options, SelectionRegistry
from tests.test_source_first_case_capsule import case_work
from tests.test_source_first_book_runner import Registry


class CompositionRegistry(Registry):
    """Keep all five exact fake models, but reject every non-composition writer call."""

    def __init__(self, **options):
        """Configure optional fake writer formatting/transport defects."""
        self.extra_brace = options.pop('extra_brace', False)
        self.writer_error = options.pop('writer_error', False)
        self.initial_formula_response = options.pop('initial_formula_response', '__default__')
        super().__init__(**options)

    def respond(self, voice, payload):
        """Assert binding survives lean view; return existing synthetic prose only."""
        assert voice == 'sutrakar' and payload['stage'].startswith('composition')
        assert 'composition_binding' in payload
        assert payload['composition_binding']['case_capsule_sha256']
        assert 'chapter' not in payload['brief']
        if self.writer_error:
            raise TimeoutError('synthetic writer timeout')
        answer = super().respond(voice, payload)
        if payload['stage'] == 'composition':
            if self.initial_formula_response == '__omit__':
                answer.pop('new_sutra', None)
            elif self.initial_formula_response != '__default__':
                answer['new_sutra'] = self.initial_formula_response
        return answer

    def generate(self, voice, adapter, prompt, system):
        """Return one extra brace only on writer output, never alter raw GPT prompt."""
        result = super().generate(voice, adapter, prompt, system)
        if self.extra_brace and voice == 'sutrakar':
            result.content += '}'
        return result


@pytest.fixture(autouse=True)
def no_credentials(monkeypatch):
    """Trip on every attempted real credential or production-registry access."""
    def forbidden(*args, **kwargs):
        """Fail any attempted live setup in an offline test."""
        pytest.fail('Real credentials/SDK registry forbidden')
    monkeypatch.setattr('scripts.run_research_book.load_project_credentials', forbidden)
    monkeypatch.setattr('src.providers.registry.ProviderRegistry', forbidden)


def write(path, value):
    """Save temporary JSON and return its exact byte hash."""
    runner.book.save(path, value)
    return runner.book.byte_hash(path)


def receipt(path):
    """Write a trusted synthetic receipt; it claims no actual source quality."""
    write(path, {'status': 'PASS', 'paid_calls': 0, 'code_sha256': runner.code_bindings(),
        'tests': [{'path': p, 'passed': 1, 'failed': 0, 'errors': 0} for p in runner.REQUIRED_TESTS]})


class SelectedProposalRegistry(SelectionRegistry):
    """Use existing distinct short-formula fixtures as actual source-phase proposals."""

    def respond(self, voice, payload):
        """Keep source-stage outputs synthetic and distinct for the selected task identities."""
        value = super().respond(voice, payload)
        if payload['stage'] == 'proposal':
            for proposal in value['proposals']:
                if proposal['number'] in (2, 3) and proposal['decision'] == 'ACCEPT':
                    proposal['proposed_sutra'] = {2: 'प्रमाणेन निर्णयः', 3: 'निष्ठया सेवा'}[proposal['number']]
        return value


def build_setup(tmp_path, monkeypatch, augment=None, numbers=(2, 3), selection_registry=None):
    """Produce actual saved selection/capsules; optional proof is attached BEFORE debate."""
    selection_root = tmp_path / 'selection-setup'; selection_root.mkdir()
    selection_args = selection_options.__wrapped__(selection_root, monkeypatch)
    if augment is not None:
        original_builder = selector.build_selection
        def augmented(*args, **kwargs):
            """Attach a supplied synthetic attested menu before any four-voice callback."""
            value = original_builder(*args, **kwargs)
            for item in value['entries']:
                item['source_packet'] = augment(deepcopy(item['source_packet']), item['candidate_id'])
            return value
        monkeypatch.setattr(selector, 'build_selection', augmented)
    selector.run(**selection_args, registry=selection_registry or SelectedProposalRegistry(), target=max(numbers))
    root = selection_args['work']
    proofs = case_work(tmp_path / 'case-proofs')
    tasks, used, keys = [], set(), set()
    for number, pair in zip(numbers, (('positive-a', 'caution-b'), ('positive-c', 'caution-d'))):
        candidate_path = root / f'candidate-{number:03d}.json'
        candidate = runner.book.load(candidate_path)
        discussion_path = root / candidate['discussion_file']
        input_path = root / candidate['discussion_file'].replace('-discussion.json', '-input.json')
        supplied, bundle = runner.book.load(input_path), runner.book.load(discussion_path)
        brief = next(b for b in supplied['briefs'] if b['number'] == number)
        sources = supplied['source_packets'][str(number)]
        capsule = build_case_capsule(number=number, brief=brief, sources=sources,
            discussion=bundle['discussion'], proposal=bundle['proposal'], peer_review=bundle['peer_review'],
            case_work_dir=proofs, used_case_ids=used, used_identity_keys=keys,
            case_slots=[{'kind': kind, 'case_id': ident, 'fit_reason_mr': 'कृत्रिम चाचणीतील स्पष्ट मर्यादित उपयोग',
                         'limitations_mr': 'ही ऐतिहासिक सत्यता प्रमाणित करणारी चाचणी नाही'}
                        for kind, ident in zip(('positive', 'caution'), pair)])
        effective, _ = apply_case_capsule(capsule, number=number, brief=brief, sources=sources,
            discussion=bundle['discussion'], proposal=bundle['proposal'], peer_review=bundle['peer_review'],
            used_case_ids=used)
        for assignment in effective['case_assignments']:
            used.add(assignment['case_id']); keys.update(assignment['identity_reservations'])
        task = {'number': number, 'brief': brief, 'source_packet': sources, 'case_capsule': capsule}
        for key, path in [('selection_input', input_path), ('selection_discussion', discussion_path),
                          ('candidate_record', candidate_path)]:
            task[key] = {'path': str(path), 'sha256': runner.book.byte_hash(path)}
        tasks.append(task)
    path = tmp_path / 'tasks.json'; task_hash = write(path, {'schema': runner.SCHEMA, 'tasks': tasks})
    gate = tmp_path / 'execution-receipt.json'; receipt(gate)
    monkeypatch.setattr(runner.book, 'require_validator_calibration', lambda path: {'status': 'PASS', 'synthetic': True})

    def no_discussion(*args, **kwargs):
        """Fail if the composition executor reruns even a single selection round."""
        pytest.fail('Previously completed four-voice discussion must not run')
    monkeypatch.setattr(ResearchCouncil, 'run_batch_discussion', no_discussion)
    return {'tasks': tasks, 'options': dict(tasks_path=path, tasks_sha256=task_hash,
        forbidden_path=selection_args['forbidden_path'], calibration_dir=tmp_path / 'calibration',
        offline_gate=gate, work=tmp_path / 'selected-composition', aggregate_budget=4.)}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    """Build the unaugmented canonical baseline through production selection wiring."""
    return build_setup(tmp_path, monkeypatch)


def repin(setup, tasks=None):
    """Explicitly bind a changed synthetic task file; never change an old registry."""
    setup['options']['tasks_sha256'] = write(setup['options']['tasks_path'],
        {'schema': runner.SCHEMA, 'tasks': setup['tasks'] if tasks is None else tasks})


def test_pilot_append_resume_uses_only_writer_and_raw_reviewer(setup):
    """Exercise real complete production orchestration, stable IDs and prefix append."""
    opts = setup['options']; repin(setup, setup['tasks'][:1]); fake = CompositionRegistry()
    before = deepcopy(setup['tasks'])
    first = runner.run(**opts, registry=fake)
    assert first['status'] == 'READY_FOR_AUTHOR_REVIEW'
    assert first['ready'][0]['number'] == 2
    draft = first['ready'][0]['draft']
    assert draft['number'] == 2 and draft['id'] == 'source-selection-N003-S002'
    assert draft['chapter'] == 2 and 'chapter' not in setup['tasks'][0]['brief']
    assert [c['voice'] for c in fake.calls] == ['sutrakar', 'validator']
    pilot_dir = opts['work'] / first['ready'][0]['composition_scope']
    pilot_bytes = (pilot_dir / 'result.json').read_bytes()
    provider = runner.book.load(pilot_dir / 'task-input.json')
    assert provider == setup['tasks'][0]
    repin(setup)
    # Receipt regeneration must not change any immutable provider/reviewer input.
    gate = runner.book.load(opts['offline_gate']); gate['note'] = 'New receipt, same exact execution seal'
    write(opts['offline_gate'], gate)
    count = len(fake.calls)
    second = runner.run(**opts, registry=fake, resume=True, target=None)
    assert [r['number'] for r in second['ready']] == [2, 3]
    assert len(fake.calls) == count + 2
    assert (pilot_dir / 'result.json').read_bytes() == pilot_bytes
    assert setup['tasks'] == before
    count = len(fake.calls)
    assert runner.run(**opts, registry=fake, resume=True, target=None) == second
    assert len(fake.calls) == count
    for call in fake.calls:
        assert call['timeout'] == 240
        if call['voice'] == 'sutrakar':
            assert call['tokens'] == 18000 and call['effort'] == 'medium'
    assert second['publication_approved'] is False and second['author_approval'] == 'PENDING'


@pytest.mark.parametrize('linguistic_field', ['grammar_mr', 'new_sutra', 'translation_mr'])
def test_later_selection_batch_retains_source_prefix_and_actual_book_comparators(tmp_path, monkeypatch, linguistic_field):
    """Different composed/proposed formulas and a held source proposal never cause a false prefix stop."""
    from tests.test_independent_review_v2 import FORMULA
    class HeldSelection(SelectedProposalRegistry):
        """Keep an accepted but peer-held source formula outside actual book drafts."""
        def respond(self, voice, payload):
            """Return real-shaped synthetic source decisions and one explicit peer hold."""
            value = super().respond(voice, payload)
            if payload['stage'] == 'proposal':
                for proposal in value['proposals']:
                    if proposal['number'] == 12:
                        proposal['proposed_sutra'] = 'निष्ठया सेवा'
                    elif proposal['number'] != 2:
                        proposal['proposed_sutra'] = 'उद्यमेन विवेकः'
            if payload['stage'] == 'peer_review' and voice == 'narada':
                for review in value['reviews']:
                    if review['number'] == 1:
                        review.update(verdict='REVIEW_REQUIRED', issues=[{
                            'field': 'business_action_mr', 'quote': 'चाचणी कृती',
                            'reason': 'Synthetic substantive source-only hold', 'severity': 'major'}])
            return value
    class LaterComposition(CompositionRegistry):
        """Reuse existing synthetic formula fixtures at a larger logical identity."""
        def respond(self, voice, payload):
            """Generate fake prose without changing the actual logical request/brief."""
            if payload['number'] == 2 and payload['stage'] == 'composition_v2_1':
                return {'patch': {'new_sutra': FORMULA, 'grammar_mr': 'चाचणीपुरती सुधारित व्याकरण चर्चा',
                                  'translation_mr': 'चाचणीपुरता सुधारित अर्थ'}}
            if payload['number'] == 12:
                value = super().respond(voice, {**payload, 'number': 3})
                value.update(summary_mr='सारांश 12', action_mr='कृती 12')
                return value
            return super().respond(voice, payload)
        def generate(self, voice, adapter, prompt, system):
            """Request one explicit grammar repair through the actual independent-review codec."""
            value = super().generate(voice, adapter, prompt, system)
            if voice == 'validator':
                payload = json.loads(prompt.split('\nEVIDENCE\n', 1)[1]); draft = payload['current_draft']
                if draft['number'] == 2 and draft['new_sutra'] != FORMULA:
                    from tests.test_independent_review_v2 import answer, issue, reference_answer, source_check
                    refs = {r['id']: r for r in payload['canonical_sources']['references']}
                    checks = [source_check(field=p['field'], source_id=p['source_id'],
                        application=p['current_claim'], source_quote=refs[p['source_id']]['original_text'])
                        for p in payload['00_review_checks']['source_claim_pairs']]
                    blocker = issue('GRAMMAR', {'rule': 'Synthetic agreement rule',
                        'explanation': 'Synthetic independent rule application'},
                        field=linguistic_field, quote=draft[linguistic_field])
                    value.content = json.dumps(reference_answer(answer('REVISION_REQUIRED',
                        issues=[blocker], source_checks=checks), payload), ensure_ascii=False)
            return value
    configured = build_setup(tmp_path, monkeypatch, numbers=(2, 12), selection_registry=HeldSelection())
    first, later = configured['tasks']
    assert first['selection_discussion']['path'] != later['selection_discussion']['path']
    root = Path(first['candidate_record']['path']).parent
    assert runner.book.load(root / 'candidate-001.json')['status'] == 'HOLD_PEER_REVIEW'
    fake = LaterComposition(); result = runner.run(**configured['options'], registry=fake, target=None)
    assert [row['number'] for row in result['ready']] == [2, 12]
    actual = result['ready'][0]['draft']['new_sutra']
    first_proposal = runner.book.load(first['candidate_record']['path'])['proposal']['proposed_sutra']
    assert actual != first_proposal
    source_prior = runner.book.load(later['selection_discussion']['path'])['discussion']['_batch']['prior_formulas']
    held_formula = runner.book.load(root / 'candidate-001.json')['proposal']['proposed_sutra']
    assert held_formula in source_prior and actual not in source_prior
    writer = json.loads(fake.calls[4]['prompt'])['input']
    assert writer['prior_formulas'] == source_prior + [actual]
    review = json.loads(fake.calls[5]['prompt'].split('\nEVIDENCE\n', 1)[1])
    assert [row['id'] for row in review['comparison_chapters']] == [result['ready'][0]['draft']['id']]
    assert [c['voice'] for c in fake.calls] == ['sutrakar', 'validator', 'sutrakar', 'validator', 'sutrakar', 'validator']
    assert fake.calls[2]['tokens'] == 6000


def test_source_hashes_and_reviewer_cache_include_full_capsule_binding(setup):
    """Inspect actual factory inputs, scoped reviewer database and current draft hash."""
    seen = []; actual = runner.SourceFirstProvider
    def construct(*args, **kwargs):
        """Observe unchanged real boundary initialization while recording source hashes."""
        assert kwargs['max_usd'] == 2. and kwargs['claude_cap_usd'] == 1.5
        assert kwargs['max_calls'] == 8
        seen.append(deepcopy(kwargs['source_hashes']))
        return actual(*args, **kwargs)
    from unittest.mock import patch
    with patch.object(runner, 'SourceFirstProvider', construct):
        result = runner.run(**setup['options'], registry=CompositionRegistry())
    task = setup['tasks'][0]
    bundle = runner.book.load(task['selection_discussion']['path'])
    effective, binding = apply_case_capsule(task['case_capsule'], number=2, brief=task['brief'],
        sources=task['source_packet'], discussion=bundle['discussion'], proposal=bundle['proposal'],
        peer_review=bundle['peer_review'], used_case_ids=set())
    assert all(seen[0][key] == value for key, value in binding.items())
    directory = setup['options']['work'] / result['ready'][0]['composition_scope']
    with sqlite3.connect(directory / 'independent-review.db') as db:
        state, request = db.execute('SELECT state,request_json FROM independent_reviews_v2').fetchone()
    assert state == 'COMPLETE'
    payload = json.loads(request)['payload']
    assert payload['current_draft'] == result['ready'][0]['draft']
    assert 'discussion' not in payload and 'proposal' not in payload
    assert (directory / 'review-raw').is_dir()


def test_changed_current_draft_cannot_reuse_old_independent_review(setup):
    """A changed council draft needs its own review; READY replay cannot pay for it."""
    opts = setup['options']; fake = CompositionRegistry()
    result = runner.run(**opts, registry=fake); count = len(fake.calls)
    directory = runner.io_path(opts['work']) / result['ready'][0]['composition_scope']
    with sqlite3.connect(directory / 'council.db') as db:
        original = db.execute("SELECT response_json FROM research_stages WHERE stage='composition'").fetchone()[0]
        changed = json.loads(original); changed['summary_mr'] += ' changed current draft'
        db.execute("UPDATE research_stages SET response_json=? WHERE stage='composition'", (json.dumps(changed),))
    with pytest.raises(runner.SourceFirstStopped):
        runner.run(**opts, registry=fake, resume=True)
    assert len(fake.calls) == count


def test_default_offline_preflight_writes_nothing(setup):
    """Verify immutable inputs and gates without constructing any provider/output."""
    assert runner.run(**setup['options']) == {'status': 'OFFLINE_PREFLIGHT_PASS', 'target': 1, 'paid_calls': 0}
    assert not setup['options']['work'].exists()


def optional_augment(damage=None):
    """Use Jason's synthetic attestation fixture; never create real saint material."""
    from tests.test_source_first_selection_runner import approved_optional_packet
    def augment(baseline, identifier):
        """Attach the optional packet to its sole mapped pair before all saved rounds."""
        if identifier != 'N003-S002':
            return baseline
        packet = approved_optional_packet(baseline)
        if damage == 'unknown':
            extra = deepcopy(packet['references'][-1]); extra['id'] = 'MRB-UNREGISTERED'
            packet['references'].append(extra)
            packet['source_contexts'][extra['id']] = deepcopy(packet['source_contexts']['MRB-STRUCTURAL-TEST'])
        elif damage == 'proof':
            packet['optional_supplement_proof']['bundle']['documents'][selector.SUPPLEMENT_MENU]['utf8'] += ' '
        elif damage == 'context':
            packet['source_contexts']['MRB-STRUCTURAL-TEST']['meaning_mr'] += ' changed'
        return packet
    return augment


def test_attested_optional_reference_survives_selection_capsule_and_composition(tmp_path, monkeypatch):
    """Approved optional context remains canonical; no source or discussion is regenerated."""
    configured = build_setup(tmp_path, monkeypatch, augment=optional_augment())
    original = deepcopy(configured['tasks'][0]); fake = CompositionRegistry()
    result = runner.run(**configured['options'], registry=fake)
    assert result['status'] == 'READY_FOR_AUTHOR_REVIEW'
    assert 'MRB-STRUCTURAL-TEST' in result['ready'][0]['draft']['references']
    assert configured['tasks'][0] == original and len(fake.calls) == 2
    writer = json.loads(fake.calls[0]['prompt'])['input']
    assert 'MRB-STRUCTURAL-TEST' in writer['sources']['source_contexts']
    assert writer['composition_binding']['original_selection_sha256'] == original['case_capsule']['selection']['selection_sha256']


@pytest.mark.parametrize('damage', ['unknown', 'proof', 'context'])
def test_optional_extras_cannot_bypass_exact_original_packet_rebuild(tmp_path, monkeypatch, damage):
    """Even hash-bound saved rounds/capsules cannot bless unknown or tampered menu data."""
    configured = build_setup(tmp_path, monkeypatch, augment=optional_augment(damage))
    def forbidden(*args, **kwargs):
        """Trip if unregistered optional evidence reaches a live provider factory."""
        pytest.fail('Unchecked optional evidence reached provider')
    monkeypatch.setattr(runner, 'create_live_provider', forbidden)
    with pytest.raises(ValueError):
        runner.run(**configured['options'], live=True, credentials_dir='never-read')
    assert not configured['options']['work'].exists()


@pytest.mark.parametrize('damage', ['capsule', 'sources', 'brief', 'used_ids', 'used_keys', 'artifact', 'pending_peer'])
def test_tamper_stops_before_provider_or_output(setup, monkeypatch, damage):
    """Reject stale source/selection/usage proofs without any execution setup."""
    task = setup['tasks'][0]
    if damage == 'capsule': task['case_capsule']['case_slots'][0]['limitations_mr'] = 'Changed without seal'
    elif damage == 'sources': task['source_packet']['references'][0]['original_text'] += ' changed'
    elif damage == 'brief': task['brief']['chapter'] = 1
    elif damage == 'used_ids':
        task['case_capsule']['used_case_ids'] = ['positive-c']
        task['case_capsule']['capsule_sha256'] = runner.book.preparation.digest({k:v for k,v in task['case_capsule'].items() if k != 'capsule_sha256'})
    elif damage == 'used_keys': task['case_capsule']['used_identity_keys'] = ['missinghistory']
    elif damage == 'artifact': Path(task['selection_input']['path']).write_text('{}')
    else:
        record_path = Path(task['candidate_record']['path']); record = runner.book.load(record_path)
        record['peer_review']['narada']['verdict'] = 'REVIEW_REQUIRED'
        task['candidate_record']['sha256'] = write(record_path, record)
    repin(setup)
    def forbidden(*args, **kwargs):
        """Trip before credentials if validation incorrectly advances."""
        pytest.fail('Invalid input reached provider setup')
    monkeypatch.setattr(runner, 'create_live_provider', forbidden)
    with pytest.raises((ValueError, KeyError)):
        runner.run(**setup['options'], live=True, credentials_dir='never-read')
    assert not setup['options']['work'].exists()


def test_aggregate_cap_reserves_entry_liability_before_next_task(setup):
    """Aggregate headroom includes held original charges and each next $2 ceiling."""
    setup['options']['aggregate_budget'] = 2.
    fake = CompositionRegistry(); result = runner.run(**setup['options'], registry=fake, target=None)
    assert result['status'] == 'BUDGET_STOP' and len(result['ready']) == 1
    assert len(fake.calls) == 2
    assert 0 < result['reservation_usd'] < 2
    assert runner.run(**setup['options'], registry=fake, resume=True, target=None) == result
    assert len(fake.calls) == 2


@pytest.mark.parametrize('fault', ['writer', 'reviewer', 'truncated'])
def test_failure_is_terminal_and_original_reservation_survives(setup, fault):
    """Provider/reviewer failures are not paid retries, including through fresh resume."""
    fake = CompositionRegistry(writer_error=fault == 'writer',
        validator_fault='truncated' if fault == 'truncated' else 'credit' if fault == 'reviewer' else None)
    with pytest.raises(runner.SourceFirstStopped): runner.run(**setup['options'], registry=fake)
    report = runner.book.load(setup['options']['work'] / 'report.json')
    assert report['ready'] == [] and report['reservation_usd'] > 0
    count = len(fake.calls)
    with pytest.raises(runner.SourceFirstStopped):
        runner.run(**setup['options'], registry=fake, resume=True)
    assert len(fake.calls) == count
    assert runner.book.load(setup['options']['work'] / 'report.json')['reservation_usd'] == report['reservation_usd']


def test_only_known_lossless_writer_framing_is_reused(setup):
    """A complete writer object plus one brace uses saved bytes, not a new SDK call."""
    fake = CompositionRegistry(extra_brace=True)
    result = runner.run(**setup['options'], registry=fake)
    assert len(result['ready']) == 1 and len(fake.calls) == 2
    directory = setup['options']['work'] / result['ready'][0]['composition_scope']
    with sqlite3.connect(directory / 'provider' / 'boundary.db') as db:
        assert db.execute('SELECT COUNT(*) FROM json_framing_recoveries').fetchone()[0] == 1
    assert runner.run(**setup['options'], registry=fake, resume=True) == result
    assert len(fake.calls) == 2


@pytest.mark.parametrize('returned', ['__omit__', 'उद्यमेन विवेकः', 'चाचणी ' * 12])
def test_initial_formula_is_existing_approved_value_not_long_response(setup, returned):
    """Transport reader-facing instructions while retaining the approved Sanskrit and cases."""
    fake = CompositionRegistry(initial_formula_response=returned)
    original = deepcopy(setup['tasks'][0]); candidate = runner.book.load(original['candidate_record']['path'])
    fixed = candidate['proposal']['proposed_sutra']
    result = runner.run(**setup['options'], registry=fake)
    assert result['ready'][0]['draft']['new_sutra'] == fixed
    assert setup['tasks'][0] == original and len(fake.calls) == 2
    writer = json.loads(fake.calls[0]['prompt'])
    assert writer['input']['fixed_initial_formula'] == fixed
    assert 'Do NOT return new_sutra' in writer['instruction']
    assert fake.calls[0]['system'] == runner.INITIAL_SYSTEM
    assert runner.INITIAL_INSTRUCTION == writer['instruction']
    assert 'Open the main exposition' in fake.calls[0]['system']
    assert 'concrete actions and temptations' in fake.calls[0]['system']
    assert 'do not retell those full stories' in writer['instruction']
    assert 'hypothetical anecdotes' in writer['instruction']
    directory = runner.io_path(setup['options']['work']) / result['ready'][0]['composition_scope']
    proof = runner.book.load(directory / 'initial-formula-binding.json')
    assert proof['canonical_formula'] == fixed and proof['new_formula_generated_offline'] is False
    assert proof['unasked_formula_present'] is (returned != '__omit__')
    if returned != '__omit__': assert proof['unasked_formula_value'] == returned
    raw = (directory / 'provider' / 'raw' / (proof['provider_slot'] + '.txt')).read_bytes()
    import hashlib
    assert hashlib.sha256(raw).hexdigest() == proof['original_raw_sha256']
    assert json.loads(raw).get('new_sutra') == (None if returned == '__omit__' else returned)
    assert runner.run(**setup['options'], registry=fake, resume=True) == result
    assert len(fake.calls) == 2


def test_prefix_and_current_code_gate_cannot_rebind_pilot(setup):
    """An existing task or implementation/calibration/cap is not an append operation."""
    fake = CompositionRegistry(); runner.run(**setup['options'], registry=fake)
    count = len(fake.calls)
    setup['tasks'][0]['case_capsule']['case_slots'][0]['fit_reason_mr'] += ' changed'
    capsule = setup['tasks'][0]['case_capsule']
    capsule['capsule_sha256'] = runner.book.preparation.digest({k:v for k,v in capsule.items() if k != 'capsule_sha256'})
    repin(setup)
    with pytest.raises(ValueError, match='prefix'): runner.run(**setup['options'], registry=fake, resume=True)
    assert len(fake.calls) == count


def test_current_code_receipt_refresh_preserves_paid_cache_and_audit(setup, monkeypatch):
    """A tested parser-code fix refreshes execution evidence without rebilling READY."""
    opts = setup['options']; fake = CompositionRegistry()
    before = runner.run(**opts, registry=fake)
    count = len(fake.calls)
    changed = deepcopy(runner.code_bindings())
    changed['src/orchestration/source_first_provider.py'] = 'f' * 64
    monkeypatch.setattr(runner, 'code_bindings', lambda: deepcopy(changed))
    monkeypatch.setattr(runner.book, 'require_validator_calibration',
                        lambda path: {'status': 'PASS', 'synthetic': True, 'fresh_report': True})
    receipt(opts['offline_gate'])
    assert runner.run(**opts, registry=fake, resume=True) == before
    assert len(fake.calls) == count
    history = runner.book.load(opts['work'] / 'execution-receipts.json')
    assert len(history) == 2
    assert history[0]['code_seal_sha256'] != history[1]['code_seal_sha256']
    assert history[0]['offline_gate_sha256'] != history[1]['offline_gate_sha256']
    assert history[0]['calibration_report_sha256'] != history[1]['calibration_report_sha256']
    manifest = runner.book.load(opts['work'] / 'run-manifest.json')
    assert 'implementation' not in manifest['binding']


@pytest.mark.parametrize('change', ['system', 'view'])
def test_actual_protocol_or_prompt_drift_stops_cached_ready(setup, monkeypatch, change):
    """Cache-safe code upgrades cannot authorize changed paid prompts or contract."""
    opts = setup['options']; fake = CompositionRegistry()
    runner.run(**opts, registry=fake); count = len(fake.calls)
    if change == 'system':
        monkeypatch.setattr(runner, 'WRITING_SYSTEM', runner.WRITING_SYSTEM + ' changed protocol')
    else:
        original = runner.writing_view
        def changed(payload):
            """Simulate a changed actual JSON request without changing its protocol label."""
            return {**original(payload), 'new_instruction': 'actual changed request'}
        monkeypatch.setattr(runner, 'writing_view', changed)
    receipt(opts['offline_gate'])
    with pytest.raises((ValueError, runner.SourceFirstStopped)):
        runner.run(**opts, registry=fake, resume=True)
    assert len(fake.calls) == count


def test_stale_receipt_and_calibration_stop_before_keys(setup, monkeypatch):
    """Do not construct a live registry on stale required tests or failed calibration."""
    opts = setup['options']; gate = runner.book.load(opts['offline_gate'])
    gate['code_sha256']['scripts/run_source_first_selected_book.py'] = '0' * 64
    write(opts['offline_gate'], gate)
    with pytest.raises(ValueError, match='offline'):
        runner.run(**opts, live=True, credentials_dir='never-read')
    assert not opts['work'].exists()
    receipt(opts['offline_gate'])
    def rejected(path):
        """Represent an unchanged real calibration gate rejecting stale evidence."""
        raise ValueError('calibration rejected')
    monkeypatch.setattr(runner.book, 'require_validator_calibration', rejected)
    with pytest.raises(ValueError, match='calibration'):
        runner.run(**opts, live=True, credentials_dir='never-read')
    assert not opts['work'].exists()


def test_valid_json_bad_schema_does_not_regenerate(setup, monkeypatch):
    """A complete but unusable writer record stops after one held attempt."""
    fake = CompositionRegistry()
    monkeypatch.setattr(fake, 'respond', lambda voice, payload: {})
    with pytest.raises(runner.SourceFirstStopped): runner.run(**setup['options'], registry=fake)
    assert len(fake.calls) == 1 and fake.calls[0]['voice'] == 'sutrakar'


def test_quality_stop_is_terminal_after_one_substantive_revision(setup):
    """An independent READY cannot override structural missing-source quality failure."""
    fake = CompositionRegistry(draft_defect='missing_source')
    result = runner.run(**setup['options'], registry=fake)
    assert result['status'] == 'QUALITY_STOP' and result['ready'] == []
    # An identical failed repair reuses the exact prior independent review.
    assert [c['voice'] for c in fake.calls] == ['sutrakar', 'validator', 'sutrakar']
    count = len(fake.calls)
    with pytest.raises(runner.SourceFirstStopped):
        runner.run(**setup['options'], registry=fake, resume=True)
    assert len(fake.calls) == count


@pytest.mark.parametrize('mode', ['formula', 'exposition'])
def test_narrow_repairs_keep_capsule_and_reserve_6000(setup, tmp_path, monkeypatch, mode):
    """Real selected writer transport retains binding/cases and bounded repair cost."""
    data = runner.validate_task(setup['tasks'][0], tmp_path, set(), set())
    original = data['task']; sources = data['effective_sources']; fake = CompositionRegistry()
    payload = {'number': 2, 'brief': original['brief'], 'sources': sources,
        'composition_binding': data['composition_binding'], 'discussion': {}, 'stage': 'composition_v2_1',
        'speaker': 'sutrakar', 'prior_formulas': [], 'forbidden_originals': [], 'used_case_ids': []}
    completion = {**payload, 'brief': {**payload['brief'], 'chapter': 2}}
    draft = runner.book.complete_entry(Registry().respond('sutrakar', payload), completion)
    payload.update(draft=deepcopy(draft), assessment={'status': 'PASS'},
                   review={'issues': [{'field': 'grammar_mr'}]})
    linguistic = {'field': 'grammar_mr', 'quote': draft['grammar_mr'],
                  'reason': 'Synthetic independently substantiated grammar defect'}
    payload['review'] = {'verdict': 'REVIEW_REQUIRED', 'outcome': 'REVISION_REQUIRED',
        'issues': [{**linguistic, 'severity': 'substantive'}],
        'typed_review': {'blocking_issues': [linguistic]}, 'review_key': 'a' * 64,
        'reviewed_draft_sha256': runner.canonical_hash(payload['draft']),
        'rubric_sha256': runner.contract_hash()}
    response = {'patch': {k: draft[k] for k in ('new_sutra', 'grammar_mr', 'translation_mr')}}
    if mode == 'exposition':
        payload['draft']['exposition'] = ['विचार ' * 450]
        payload['assessment'] = {'status': 'NEEDS_REVISION', 'issues': [
            'exposition has 450 Devanagari word tokens; at least 500 required']}
        payload['review'] = {'verdict': 'PASS', 'issues': []}
        response = {'additional_paragraph_mr': 'चाचणी ' * 160,
                    'new_sutra': 'अनाहूतं सूत्रम्'}
    monkeypatch.setattr(fake, 'respond', lambda voice, view: deepcopy(response))
    provider = runner.SourceFirstProvider(tmp_path / ('repair-' + mode), fake,
        source_hashes=data['composition_binding'], max_usd=2., max_calls=8, claude_cap_usd=1.5)
    calls = runner.CompositionCalls(provider, tmp_path, data['proposal'], data['composition_binding'])
    before = deepcopy(payload); result = calls.voice('sutrakar', payload)
    assert payload == before and result['examples'] == sources['examples']
    assert result['references'] == draft['references']
    assert result['new_sutra'] == draft['new_sutra']
    if mode == 'exposition':
        proofs = list((tmp_path / 'protected-formula-bindings').glob('*.json'))
        assert len(proofs) == 1
        assert runner.book.load(proofs[0])['unasked_formula_value'] == response['new_sutra']
    assert fake.calls[0]['tokens'] == 6000 and fake.calls[0]['effort'] == 'medium'
    assert json.loads(fake.calls[0]['prompt'])['input']['composition_binding'] == data['composition_binding']
    rate = runner.book.RATES['anthropic:claude-sonnet-5-5']
    assert provider.spend_guard.reserved_usd == pytest.approx((10*rate['input']+6000*rate['output'])/1e6)


@pytest.mark.parametrize('kind', ['summary', 'exposition', 'source'])
def test_nonlinguistic_independent_issue_cannot_replace_current_formula(setup, kind):
    """Real typed prose/source feedback triggers repair, never an unsolicited formula change."""
    from tests.test_independent_review_v2 import FORMULA, answer, issue, reference_answer, source_check
    class ProseRepair(CompositionRegistry):
        """Return one substantive prose issue and an unasked formula in its repair."""
        def __init__(self):
            """Track exactly one actual independent request for a prose correction."""
            super().__init__(); self.requested = False
        def respond(self, voice, payload):
            """Change only requested prose deliberately, while attempting forbidden Sanskrit replacement."""
            value = super().respond(voice, payload)
            if kind == 'source' and payload['stage'] == 'composition':
                value['comparative_mr'][0]['explanation_mr'] = 'मूळ स्रोत प्रत्येक व्यवसायाला चोवीस तासांत सुरू होण्याचा आदेश देतो.'
            if payload['stage'] == 'composition_v2_1':
                value['new_sutra'] = FORMULA
                if kind == 'summary': value['summary_mr'] = 'सुधारित चाचणी सारांश'
                if kind == 'exposition': value['exposition'] = ['नवीन विचार ' * 510]
            return value
        def generate(self, voice, adapter, prompt, system):
            """Use real IndependentReviewer codec and current literal evidence for the first defect."""
            response = super().generate(voice, adapter, prompt, system)
            if voice == 'validator' and not self.requested:
                self.requested = True
                payload = json.loads(prompt.split('\nEVIDENCE\n', 1)[1]); draft = payload['current_draft']
                refs = {r['id']: r for r in payload['canonical_sources']['references']}
                pairs = payload['00_review_checks']['source_claim_pairs']
                checks = [source_check(field=p['field'], source_id=p['source_id'], application=p['current_claim'],
                          source_quote=refs[p['source_id']]['original_text']) for p in pairs]
                if kind == 'source':
                    pair = pairs[0]
                    checks[0] = source_check('FALSE_ATTRIBUTION', field=pair['field'], source_id=pair['source_id'],
                        claim=pair['current_claim'], application='', source_quote=refs[pair['source_id']]['original_text'])
                    defect = issue('SOURCE_DISTORTION', {'source_id': pair['source_id'],
                        'source_quote': refs[pair['source_id']]['original_text'],
                        'contradiction': 'The canonical source contains no mandatory 24-hour business launch rule.'},
                        field=pair['field'], quote=pair['current_claim'])
                else:
                    field = 'summary_mr' if kind == 'summary' else 'exposition.0'
                    defect = issue('GRAMMAR', {'rule': 'Synthetic Marathi prose agreement',
                        'explanation': 'Synthetic defect in prose, not in the Sanskrit formula.'},
                        field=field, quote=draft['summary_mr'] if kind == 'summary' else draft['exposition'][0])
                response.content = json.dumps(reference_answer(answer('REVISION_REQUIRED',
                    issues=[defect], source_checks=checks), payload), ensure_ascii=False)
            return response
    fake = ProseRepair(); original = deepcopy(setup['tasks'][0])
    proposal = runner.book.load(original['candidate_record']['path'])['proposal']['proposed_sutra']
    result = runner.run(**setup['options'], registry=fake)
    assert result['status'] == 'READY_FOR_AUTHOR_REVIEW'
    assert result['ready'][0]['draft']['new_sutra'] == proposal != FORMULA
    assert setup['tasks'][0] == original
    assert [c['voice'] for c in fake.calls] == ['sutrakar', 'validator', 'sutrakar', 'validator']
    repair = json.loads(fake.calls[2]['prompt'])
    assert repair['input']['fixed_repair_formula'] == proposal
    assert 'Do NOT return new_sutra' in repair['instruction']
    directory = runner.io_path(setup['options']['work']) / result['ready'][0]['composition_scope']
    proof = runner.book.load(next((directory / 'protected-formula-bindings').glob('*.json')))
    assert proof['canonical_current_formula'] == proposal
    assert proof['unasked_formula_value'] == FORMULA and proof['formula_change_authorized'] is False
    raw = (directory / 'provider' / 'raw' / (proof['provider_slot'] + '.txt')).read_text(encoding='utf-8')
    assert json.loads(raw)['new_sutra'] == FORMULA
    assert runner.run(**setup['options'], registry=fake, resume=True) == result
    assert len(fake.calls) == 4


def test_nonlinguistic_repair_retains_already_revised_current_formula(setup, tmp_path, monkeypatch):
    """A current formula from an earlier linguistic fix is never reset to initial proposal."""
    from tests.test_independent_review_v2 import FORMULA
    data = runner.validate_task(setup['tasks'][0], tmp_path, set(), set())
    original, fake = data['task'], CompositionRegistry()
    payload = {'number': 2, 'brief': original['brief'], 'sources': data['effective_sources'],
        'composition_binding': data['composition_binding'], 'discussion': {}, 'stage': 'composition_v2_1',
        'speaker': 'sutrakar', 'prior_formulas': [], 'forbidden_originals': [], 'used_case_ids': []}
    draft = runner.book.complete_entry(Registry().respond('sutrakar', payload),
        {**payload, 'brief': {**payload['brief'], 'chapter': 2}})
    draft['new_sutra'] = FORMULA
    payload.update(draft=deepcopy(draft), assessment={'status': 'PASS'},
                   review={'verdict': 'REVIEW_REQUIRED', 'issues': [{'field': 'summary_mr'}]})
    response = {**deepcopy(draft), 'new_sutra': data['proposal']['proposed_sutra'],
                'summary_mr': 'सुधारित चाचणी सारांश'}
    monkeypatch.setattr(fake, 'respond', lambda voice, view: deepcopy(response))
    provider = runner.SourceFirstProvider(tmp_path / 'current-formula-provider', fake,
        source_hashes=data['composition_binding'], max_usd=2., max_calls=8, claude_cap_usd=1.5)
    calls = runner.CompositionCalls(provider, tmp_path, data['proposal'], data['composition_binding'])
    before = deepcopy(payload); result = calls.voice('sutrakar', payload)
    assert result['new_sutra'] == FORMULA != data['proposal']['proposed_sutra']
    assert payload == before and len(fake.calls) == 1


def editorial_fixture(tmp_path, monkeypatch, *, failed=False, both=False):
    """Create real fake-paid original/COMPLETE editorial records, never production data."""
    monkeypatch.setattr(runner, 'code_bindings', lambda: {
        'selected-component': runner.book.byte_hash(Path(runner.__file__)),
        'focused-tests': runner.book.byte_hash(Path(__file__))})
    data = build_setup(tmp_path, monkeypatch)
    class FailedSelector(CompositionRegistry):
        """Reproduce a real failed fifth selector after one complete short draft."""
        def respond(self, voice, payload):
            """Supply a genuine 466-word exposition for the original failed entry."""
            answer = super().respond(voice, payload)
            answer['exposition'] = ['विचार ' * 466]
            return answer
        def generate(self, voice, adapter, prompt, system):
            """Keep the SDK SUCCESS but choose the formula ID for an exposition blocker."""
            answer = super().generate(voice, adapter, prompt, system)
            if voice == 'validator':
                payload = json.loads(prompt.split('\nEVIDENCE\n', 1)[1]); value = json.loads(answer.content)
                ref = next(k for k, v in payload['evidence_selection']['catalog'].items() if v['field'] == 'new_sutra')
                value.update(outcome='REVISION_REQUIRED', blocking_issues=[{'category': 'MECHANICAL',
                    'draft_ref': ref, 'reason': 'Real minimum failure in synthetic fixture', 'evidence': {'rule': 'exposition_minimum'}}])
                answer.content = json.dumps(value, ensure_ascii=False)
            return answer
    if failed:
        with pytest.raises(runner.SourceFirstStopped):
            runner.run(**data['options'], registry=FailedSelector())
    else:
        runner.run(**data['options'], registry=CompositionRegistry(), target=None if both else 1)
    origin = data['options']['work']; entries, external, canonical = [], {}, []
    old_total = runner.reserved_usd(origin, [runner.validate_task(data['tasks'][0], tmp_path, set(), set())])
    if both:
        old_total = sum(sqlite3.connect(p).execute('SELECT SUM(reservation_usd) FROM council_dispatch_audit').fetchone()[0]
                        for p in origin.rglob('dispatch.db'))
    added = 0.; used, keys, prior = set(), set(), []
    for index, task in enumerate(data['tasks'][:2 if both else 1]):
        validated = runner.validate_task(task, tmp_path, used, keys)
        _, directory, old, original, origin_proof = runner._origin(validated, {
            'path': str(origin), 'manifest_sha256': runner.book.byte_hash(origin / 'run-manifest.json')})
        draft = deepcopy(old); draft['exposition'].append('स्पष्ट विचार ' * 50)
        draft['summary_mr'] = 'संपादित सारांश ' + str(task['number'])
        provenance = {'old_draft_sha256': runner.canonical_hash(old), 'new_draft_sha256': runner.canonical_hash(draft),
            'rfc6902_patch_for_bare_draft': [
                {'op': 'test', 'path': '/exposition', 'value': old['exposition']},
                {'op': 'replace', 'path': '/exposition', 'value': draft['exposition']},
                {'op': 'test', 'path': '/summary_mr', 'value': old['summary_mr']},
                {'op': 'replace', 'path': '/summary_mr', 'value': draft['summary_mr']}]}
        provenance['parent_result' if original else 'parent_composition'] = origin_proof
        edit = tmp_path / ('edit-' + str(task['number'])); edit.mkdir()
        provider = runner.SourceFirstProvider(edit / 'provider', CompositionRegistry(), source_hashes={'editorial': 'a' * 64},
            max_usd=.25, max_calls=1, claude_cap_usd=.1)
        calls = runner.book.WritingCalls(provider, edit)
        reviewer = runner.IndependentReviewer(edit / 'review.db', calls.validator)
        review = reviewer.review(draft, validated['effective_sources'], prior)
        added += provider.dispatcher.reserved_usd
        peers = {v: next(r for r in validated['bundle']['peer_review'][v]['reviews'] if r['number'] == task['number'])
                 for v in runner.VOICES[:-1]}
        result = deepcopy(original) if original else {'discussion': validated['bundle']['discussion'],
            'proposal': validated['proposal'], 'peer_review': peers, 'revisions': 0, 'review_history': []}
        result.update(draft=draft, review=review, assessment=runner.assess_source_first_entry(draft,
            validated['effective_sources'], runner._effective_prior(validated, [p['formula'] for p in prior]),
            runner.book.load(data['options']['forbidden_path']), used),
            status='READY_FOR_AUTHOR_REVIEW', editorial_provenance=provenance)
        result['review_history'].append({'stage': 'editorial', 'review': review, 'draft_sha256': runner.canonical_hash(draft)})
        path = edit / 'result-reviewed.json'; write(path, result)
        entries.append({'number': task['number'], 'result': {'path': str(path), 'sha256': runner.book.byte_hash(path)},
            'review_db': str(edit / 'review.db'), 'origin_work': {'path': str(origin), 'manifest_sha256': runner.book.byte_hash(origin / 'run-manifest.json')},
            'task_sha256': validated['task_sha256'], 'provenance_sha256': runner.canonical_hash(provenance)})
        external[str(edit / 'provider/dispatch.db')] = runner.book.byte_hash(edit / 'provider/dispatch.db')
        canonical.append(result)
        used.update(a['case_id'] for a in validated['effective_sources']['case_assignments'])
        keys.update(k for a in validated['effective_sources']['case_assignments'] for k in a['identity_reservations'])
        prior.append({'id': draft['id'], 'formula': draft['new_sutra'], 'decision_mr': draft['summary_mr'], 'action_mr': draft['action_mr']})
    manifest = {'schema': runner.EDITORIAL_SCHEMA, 'entries': entries,
                'spend_lineage': [{'path': p, 'sha256': h} for p, h in external.items()]}
    authority_path = tmp_path / 'editorial-authority.json'
    data.update(editorial_manifest=manifest, authority_path=authority_path, canonical=canonical,
                expected_held=old_total + added, origin=origin)
    write(authority_path, manifest)
    data['authority'] = {'path': str(authority_path), 'sha256': runner.book.byte_hash(authority_path)}
    receipt(data['options']['offline_gate'])
    return data


def repin_editorial(data):
    """Explicitly pin a deliberately changed synthetic authority for a negative test."""
    write(data['authority_path'], data['editorial_manifest'])
    data['authority']['sha256'] = runner.book.byte_hash(data['authority_path'])


def test_editorial_failed_entry_continues_without_old_calls_and_keeps_current_comparators(tmp_path, monkeypatch):
    """Actual failed review remains immutable; only the later task makes two fake calls."""
    data = editorial_fixture(tmp_path, monkeypatch, failed=True)
    directory = data['origin'] / runner.validate_task(data['tasks'][0], tmp_path, set(), set())['scope']
    before = {str(p): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    fake = CompositionRegistry()
    result = runner.run(**data['options'], registry=fake, resume=True, target=None,
        verified_editorial_results=data['authority'])
    assert result['status'] == 'READY_FOR_AUTHOR_REVIEW' and len(fake.calls) == 2
    assert result['ready'][0]['canonical_source'] == 'verified_editorial_result'
    assert result['ready'][0]['draft'] == data['canonical'][0]['draft']
    payload = json.loads(fake.calls[1]['prompt'].split('\nEVIDENCE\n', 1)[1])
    assert payload['comparison_chapters'][0]['decision_mr'] == data['canonical'][0]['draft']['summary_mr']
    saved_inputs = runner.book.load(data['origin'] / result['ready'][1]['composition_scope'] / 'writing-inputs.json')
    assert sorted(next(iter(saved_inputs.values()))['used_case_ids']) == sorted(
        c['case_id'] for c in data['canonical'][0]['draft']['examples'])
    assert all(Path(p).read_bytes() == raw for p, raw in before.items())
    assert runner.book.load(directory / 'entry-state.json')['state'] == 'FAILED'
    with pytest.raises(ValueError, match='explicit current authority'):
        runner.run(**data['options'], registry=fake, resume=True, target=None)
    assert runner.run(**data['options'], registry=fake, resume=True, target=None,
        verified_editorial_results=data['authority'])['ready'] == result['ready']
    assert len(fake.calls) == 2


def test_editorial_fork_deduplicates_all_external_spend_and_uses_no_provider(tmp_path, monkeypatch):
    """Adopt two current canonical chapters into a new policy root, retaining all old spend."""
    data = editorial_fixture(tmp_path, monkeypatch, both=True)
    manifest = data['editorial_manifest']
    for path in data['origin'].rglob('dispatch.db'):
        manifest['spend_lineage'].append({'path': str(path), 'sha256': runner.book.byte_hash(path)})
    manifest['spend_lineage'].append(deepcopy(manifest['spend_lineage'][0]))
    repin_editorial(data)
    before = {str(p): p.read_bytes() for p in data['origin'].rglob('*') if p.is_file()}
    def forbidden(*args, **kwargs):
        """No provider or reviewer constructor is permitted on an adopted prefix."""
        pytest.fail('Adoption constructed a provider/reviewer')
    monkeypatch.setattr(runner, 'SourceFirstProvider', forbidden)
    monkeypatch.setattr(runner, 'IndependentReviewer', forbidden)
    options = {**data['options'], 'work': tmp_path / 'fork'}
    result = runner.run(**options, registry=object(), target=None, writer_policy=runner.WRITER_V3,
        verified_editorial_results=data['authority'])
    assert result['reservation_usd'] == pytest.approx(data['expected_held'])
    assert [r['draft'] for r in result['ready']] == [r['draft'] for r in data['canonical']]
    assert not list(options['work'].rglob('boundary.db'))
    assert all(Path(p).read_bytes() == raw for p, raw in before.items())
    assert runner.run(**options, registry=object(), target=None, resume=True, writer_policy=runner.WRITER_V3,
        verified_editorial_results=data['authority'])['ready'] == result['ready']


@pytest.mark.parametrize('fault', ['FAILED', 'RUNNING', 'missing_row', 'request', 'raw', 'forged_review', 'formula', 'cases', 'provenance', 'assessment', 'short', 'undocumented'])
def test_editorial_invalid_authority_stops_before_any_provider(tmp_path, monkeypatch, fault):
    """A PASS-shaped JSON never replaces real current COMPLETE evidence and origin proof."""
    data = editorial_fixture(tmp_path, monkeypatch, failed=True)
    item = data['editorial_manifest']['entries'][0]; path = Path(item['result']['path']); result = runner.book.load(path)
    if fault in ('FAILED', 'RUNNING', 'missing_row', 'request', 'raw'):
        with sqlite3.connect(item['review_db']) as db:
            if fault in ('FAILED', 'RUNNING'):
                db.execute('UPDATE independent_reviews_v2 SET state=?', (fault,))
            elif fault == 'missing_row':
                db.execute('DELETE FROM independent_reviews_v2')
            elif fault == 'request':
                db.execute("UPDATE independent_reviews_v2 SET request_json='{}'")
            else:
                db.execute("UPDATE independent_reviews_v2 SET response_json='{}'")
    else:
        if fault == 'forged_review': result['review']['review_key'] = '0' * 64
        if fault == 'formula': result['draft']['new_sutra'] = 'निष्ठया सेवा'
        if fault == 'cases': result['draft']['examples'][0]['text_mr'] += ' बदल'
        if fault == 'provenance': item['provenance_sha256'] = '0' * 64
        if fault == 'assessment': result['assessment'] = {'status': 'NEEDS_REVISION', 'issues': ['not ready']}
        if fault == 'short': result['draft']['exposition'] = ['विचार ' * 466]
        if fault == 'undocumented': result['draft']['summary_mr'] += ' अनोंदित बदल'
        if fault in ('short', 'undocumented'):
            result['editorial_provenance']['new_draft_sha256'] = runner.canonical_hash(result['draft'])
            item['provenance_sha256'] = runner.canonical_hash(result['editorial_provenance'])
        item['result']['sha256'] = write(path, result)
    repin_editorial(data)
    def forbidden(*args, **kwargs):
        """Reject any live/fake provider construction while authority is unverified."""
        pytest.fail('Unverified authority reached provider')
    monkeypatch.setattr(runner, 'SourceFirstProvider', forbidden)
    with pytest.raises((ValueError, KeyError)):
        runner.run(**data['options'], registry=object(), resume=True,
            verified_editorial_results=data['authority'])


def test_editorial_external_spend_omission_or_cap_cannot_refund_failure(tmp_path, monkeypatch):
    """External review charges are mandatory even for a same-root failed-entry adoption."""
    data = editorial_fixture(tmp_path, monkeypatch, failed=True)
    original = deepcopy(data['editorial_manifest']); data['editorial_manifest']['spend_lineage'] = []
    repin_editorial(data)
    with pytest.raises(ValueError, match='spend lineage'):
        runner.run(**data['options'], registry=object(), resume=True, verified_editorial_results=data['authority'])
    data['editorial_manifest'] = original
    for path in data['origin'].rglob('dispatch.db'):
        original['spend_lineage'].append({'path': str(path), 'sha256': runner.book.byte_hash(path)})
    repin_editorial(data)
    with pytest.raises(runner.SourceFirstStopped, match='aggregate cap'):
        runner.run(**{**data['options'], 'work': tmp_path / 'tiny-fork', 'aggregate_budget': data['expected_held'] / 2},
            registry=object(), verified_editorial_results=data['authority'])
    assert not (tmp_path / 'tiny-fork').exists()


def test_writer_v3_cannot_silently_change_existing_protocol(tmp_path, monkeypatch):
    """Old manifest/cache identity stays exact; new writing policy needs its own root."""
    data = editorial_fixture(tmp_path, monkeypatch)
    old = runner.book.load(data['origin'] / 'run-manifest.json')
    assert old['binding']['protocol'] == runner.protocol_binding()
    with pytest.raises(ValueError, match='Frozen protocol'):
        runner.run(**data['options'], registry=object(), resume=True, writer_policy=runner.WRITER_V3)


def test_editorial_fork_cannot_rewrite_an_existing_unadopted_original(tmp_path, monkeypatch):
    """A missing canonical authority never turns an old written entry into new Claude work."""
    data = editorial_fixture(tmp_path, monkeypatch, both=True)
    data['editorial_manifest']['entries'] = data['editorial_manifest']['entries'][:1]
    for path in data['origin'].rglob('dispatch.db'):
        data['editorial_manifest']['spend_lineage'].append({'path': str(path), 'sha256': runner.book.byte_hash(path)})
    repin_editorial(data)
    with pytest.raises(ValueError, match='no fork rewrite'):
        runner.run(**{**data['options'], 'work': tmp_path / 'missing-authority-fork'}, registry=object(), target=None,
            verified_editorial_results=data['authority'], writer_policy=runner.WRITER_V3)
    assert not (tmp_path / 'missing-authority-fork').exists()


@pytest.mark.parametrize('promote_offered', [False, True])
def test_writer_v3_selected_only_and_word_buffer_are_explicit_future_policy(tmp_path, monkeypatch, promote_offered):
    """Registered offered extras stay context; only accepted IDs may become citations."""
    monkeypatch.setattr(runner, 'code_bindings', lambda: {
        'selected-component': runner.book.byte_hash(Path(runner.__file__)),
        'focused-tests': runner.book.byte_hash(Path(__file__))})
    class SubsetSelection(SelectedProposalRegistry):
        """Offer an attested optional menu without selecting it for the proposal."""
        def respond(self, voice, payload):
            """Keep existing verified references but exclude the optional menu from selection."""
            answer = super().respond(voice, payload)
            if payload['stage'] == 'proposal':
                for row in answer['proposals']:
                    row['selected_source_ids'] = [ident for ident in row['selected_source_ids'] if not ident.startswith('MRB-')]
            return answer
    data = build_setup(tmp_path, monkeypatch, augment=optional_augment(), selection_registry=SubsetSelection())
    class SelectedOnlyWriter(CompositionRegistry):
        """Observe the explicit allowlist on the actual composition transport."""
        def respond(self, voice, payload):
            """Optionally reproduce the real offered-source promotion failure."""
            answer = super().respond(voice, payload)
            assert payload['permitted_source_ids']
            if not promote_offered:
                allowed = set(payload['permitted_source_ids'])
                answer['references'] = [ident for ident in answer['references'] if ident in allowed]
                answer['comparative_mr'] = [row for row in answer['comparative_mr'] if row['source_id'] in allowed]
            return answer
    fake = SelectedOnlyWriter(); before = deepcopy(data['tasks'])
    if promote_offered:
        with pytest.raises(runner.SourceFirstStopped):
            runner.run(**data['options'], registry=fake, writer_policy=runner.WRITER_V3)
        assert len(fake.calls) == 1 and fake.calls[0]['voice'] == 'sutrakar'
    else:
        report = runner.run(**data['options'], registry=fake, writer_policy=runner.WRITER_V3)
        allowed = json.loads(fake.calls[0]['prompt'])['input']['permitted_source_ids']
        assert set(report['ready'][0]['draft']['references']) == set(allowed)
        assert '600–700' in json.loads(fake.calls[0]['prompt'])['instruction']
        assert len(fake.calls) == 2
    request = json.loads(fake.calls[0]['prompt'])
    assert any(row['id'].startswith('MRB-') for row in request['input']['sources']['references'])
    assert not any(ident.startswith('MRB-') for ident in request['input']['permitted_source_ids'])
    assert data['tasks'] == before
    assert runner.book.load(data['options']['work'] / 'run-manifest.json')['binding']['protocol'] != runner.protocol_binding()


class WordFloorRegistry(CompositionRegistry):
    """Return controlled initial counts and one paragraph-only completion through real dispatch."""

    def __init__(self, words=450, completion=None, bad_selector=False):
        """Configure bounded fake text/selector failures without any real API access."""
        super().__init__(); self.words = words; self.bad_selector = bad_selector
        self.completion = {'additional_paragraph_mr': 'स्पष्ट विचार ' * 80} if completion is None else completion

    def respond(self, voice, payload):
        """Never compose another chapter during the paragraph-only call."""
        if payload['stage'] == 'composition_word_floor_completion':
            assert voice == 'sutrakar' and payload['fixed_formula']
            assert 'examples' not in payload and 'sources' not in payload
            assert payload['initial_exposition_word_count'] == self.words
            return deepcopy(self.completion)
        answer = super().respond(voice, payload)
        if payload['stage'] == 'composition':
            answer['exposition'] = ['विचार ' * self.words]
        return answer

    def generate(self, voice, adapter, prompt, system):
        """Optionally reproduce the actual invalid exposition selector on a genuine short draft."""
        answer = super().generate(voice, adapter, prompt, system)
        if voice == 'validator' and self.bad_selector:
            payload = json.loads(prompt.split('\nEVIDENCE\n', 1)[1]); raw = json.loads(answer.content)
            ref = next(k for k, v in payload['evidence_selection']['catalog'].items() if v['field'] == 'new_sutra')
            raw.update(outcome='REVISION_REQUIRED', blocking_issues=[{'category': 'MECHANICAL',
                'draft_ref': ref, 'reason': 'Synthetic genuine word floor', 'evidence': {'rule': 'exposition_minimum'}}])
            answer.content = json.dumps(raw, ensure_ascii=False)
        return answer


@pytest.fixture
def word_floor_setup(tmp_path, monkeypatch):
    """Seal only the owned component for focused fake tests while shared code is coordinated."""
    monkeypatch.setattr(runner, 'code_bindings', lambda: {
        'selected-component': runner.book.byte_hash(Path(runner.__file__)),
        'focused-tests': runner.book.byte_hash(Path(__file__))})
    return build_setup(tmp_path, monkeypatch)


@pytest.mark.parametrize('words', [400, 450, 499, 500])
def test_word_floor_runs_once_before_fifth_and_replays_without_new_calls(word_floor_setup, words):
    """Under500 gets exactly one6000-token completion; sufficient drafts keep the normal two calls."""
    data = word_floor_setup; fake = WordFloorRegistry(words=words)
    before_protocol = runner.protocol_binding()
    result = runner.run(**data['options'], registry=fake, complete_word_floor=True)
    expected = ['sutrakar', 'sutrakar', 'validator'] if words < 500 else ['sutrakar', 'validator']
    assert [call['voice'] for call in fake.calls] == expected
    assert result['status'] == 'READY_FOR_AUTHOR_REVIEW'
    draft = result['ready'][0]['draft']; directory = data['options']['work'] / result['ready'][0]['composition_scope']
    review_payload = json.loads(fake.calls[-1]['prompt'].split('\nEVIDENCE\n', 1)[1])
    assert review_payload['00_review_checks']['exposition_word_count'] >= 500
    assert runner.book.load(data['options']['work'] / 'run-manifest.json')['binding']['protocol'] == before_protocol
    assert runner.book.load(data['options']['work'] / 'execution-receipts.json')[-1]['complete_word_floor'] is True
    if words < 500:
        assert fake.calls[1]['tokens'] == 6000 and fake.calls[1]['effort'] == 'medium'
        initial = runner.book.load(directory / 'word-floor-initial-draft.json')
        assert {k:v for k,v in initial.items() if k != 'exposition'} == {k:v for k,v in draft.items() if k != 'exposition'}
        assert draft['exposition'][1:] == initial['exposition']
        proof = runner.book.load(directory / 'word-floor-completion-proof.json')
        assert proof['initial_words'] == words and proof['merged_words'] == words + 160
        assert proof['initial_draft_sha256'] == runner.canonical_hash(initial)
        assert proof['merged_draft_sha256'] == runner.canonical_hash(draft)
        assert proof['validator_calls_before_merge'] == 0 and proof['provider_calls'] == 1
    else:
        assert not (directory / 'word-floor-completion-proof.json').exists()
    # The option may be omitted for later future entries; old completion proofs
    # remain mandatory and replay only SUCCESS caches, never a second SDK call.
    count = len(fake.calls)
    again = runner.run(**data['options'], registry=fake, resume=True)
    assert again['ready'] == result['ready'] and len(fake.calls) == count


@pytest.mark.parametrize('words,completion,calls', [
    (399, {'additional_paragraph_mr':'विचार ' * 160}, 1),
    (450, {'additional_paragraph_mr':'विचार ' * 10}, 2),
    (450, {'new_sutra':'निष्ठया सेवा', 'additional_paragraph_mr':'विचार ' * 160}, 2),
    (450, {'additional_paragraph_mr':None}, 2),
    (450, {'additional_paragraph_mr':'विचार ' * 80 + '\n\n' + 'चिंतन ' * 80}, 2)])
def test_word_floor_unrepaired_or_unknown_shape_never_reaches_validator(word_floor_setup, words, completion, calls):
    """A bad first/only completion stops durably with zero fifth calls and no retry."""
    data = word_floor_setup; fake = WordFloorRegistry(words, completion)
    with pytest.raises(runner.SourceFirstStopped):
        runner.run(**data['options'], registry=fake, complete_word_floor=True)
    assert len(fake.calls) == calls and all(call['voice'] == 'sutrakar' for call in fake.calls)
    with pytest.raises(runner.SourceFirstStopped):
        runner.run(**data['options'], registry=fake, complete_word_floor=True, resume=True)
    assert len(fake.calls) == calls


def test_word_floor_source_drift_stops_without_completion_or_fifth(word_floor_setup, monkeypatch):
    """Mutation between initial dispatch and completion cannot become new source authority."""
    original = runner.CompositionCalls.transport
    def drift(self, payload, cache_only=False):
        """Inject a scoped in-memory drift only after the original request was durably saved."""
        answer = original(self, payload, cache_only)
        payload['sources']['references'][0]['meaning_mr'] += ' बदल'
        return answer
    monkeypatch.setattr(runner.CompositionCalls, 'transport', drift)
    fake = WordFloorRegistry()
    with pytest.raises(runner.SourceFirstStopped):
        runner.run(**word_floor_setup['options'], registry=fake, complete_word_floor=True)
    assert [row['voice'] for row in fake.calls] == ['sutrakar']


def test_word_floor_saved_proof_is_mandatory_on_ready_replay(word_floor_setup):
    """Deleting completion proof never permits another completion or fifth charge."""
    data = word_floor_setup; fake = WordFloorRegistry()
    result = runner.run(**data['options'], registry=fake, complete_word_floor=True)
    directory = data['options']['work'] / result['ready'][0]['composition_scope']
    (directory / 'word-floor-completion-proof.json').unlink()
    with pytest.raises(runner.SourceFirstStopped):
        runner.run(**data['options'], registry=fake, resume=True)
    assert len(fake.calls) == 3


def test_word_floor_default_false_preserves_original_two_call_failure(word_floor_setup):
    """Opt-out retains the old raw/FAILED review behavior and protocol without completion."""
    data = word_floor_setup; fake = WordFloorRegistry(bad_selector=True)
    with pytest.raises(runner.SourceFirstStopped):
        runner.run(**data['options'], registry=fake)
    assert [call['voice'] for call in fake.calls] == ['sutrakar', 'validator']
    assert not list(data['options']['work'].rglob('word-floor-execution-policy.json'))


def test_word_floor_same_root_authority_append_retains_old_audits_and_failed_local_spend(tmp_path, monkeypatch):
    """Append a canonical correction in the active adopted root, never a recursive fork."""
    data = editorial_fixture(tmp_path, monkeypatch, failed=True)
    for path in data['origin'].rglob('dispatch.db'):
        data['editorial_manifest']['spend_lineage'].append({'path': str(path), 'sha256': runner.book.byte_hash(path)})
    repin_editorial(data)
    options = {**data['options'], 'work':tmp_path / 'active-v3'}
    short = WordFloorRegistry(bad_selector=True)
    with pytest.raises(runner.SourceFirstStopped):
        runner.run(**options, registry=short, target=None, writer_policy=runner.WRITER_V3,
                   verified_editorial_results=data['authority'])
    assert len(short.calls) == 2
    previous = runner.book.load(options['work'] / 'editorial-adoption-registry.json')['external_audits']
    used = {c['case_id'] for c in data['canonical'][0]['draft']['examples']}
    first = runner.validate_task(data['tasks'][0], tmp_path, set(), set())
    keys = {k for a in first['effective_sources']['case_assignments'] for k in a['identity_reservations']}
    task = runner.validate_task(data['tasks'][1], tmp_path, used, keys)
    origin_ref = {'path':str(options['work']), 'manifest_sha256':runner.book.byte_hash(options['work']/'run-manifest.json')}
    _, directory, old, original, old_proof = runner._origin(task, origin_ref)
    assert original is None
    untouched = {str(p):p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    draft = deepcopy(old); draft['exposition'].append('स्पष्ट विचार ' * 50)
    provenance = {'old_draft_sha256':runner.canonical_hash(old),'new_draft_sha256':runner.canonical_hash(draft),
        'parent_composition':old_proof,'rfc6902_patch_for_bare_draft':[
            {'op':'test','path':'/exposition','value':old['exposition']},
            {'op':'replace','path':'/exposition','value':draft['exposition']}]}
    edit = tmp_path/'edit-active';edit.mkdir()
    provider = runner.SourceFirstProvider(edit/'provider',CompositionRegistry(),source_hashes={'editorial':'b'*64},
        max_usd=.25,max_calls=1,claude_cap_usd=.1)
    callback = runner.book.WritingCalls(provider,edit)
    prior = [{'id':d['draft']['id'],'formula':d['draft']['new_sutra'],
        'decision_mr':d['draft']['summary_mr'],'action_mr':d['draft']['action_mr']} for d in data['canonical']]
    review = runner.IndependentReviewer(edit/'review.db',callback.validator).review(draft,task['effective_sources'],prior)
    peers = {v:next(p for p in task['bundle']['peer_review'][v]['reviews'] if p['number']==task['number']) for v in runner.VOICES[:-1]}
    result = {'draft':draft,'review':review,'assessment':runner.assess_source_first_entry(draft,task['effective_sources'],
        runner._effective_prior(task,[p['formula'] for p in prior]),runner.book.load(options['forbidden_path']),used),
        'discussion':task['bundle']['discussion'],'proposal':task['proposal'],'peer_review':peers,'revisions':0,
        'review_history':[{'stage':'editorial','review':review,'draft_sha256':runner.canonical_hash(draft)}],
        'status':'READY_FOR_AUTHOR_REVIEW','editorial_provenance':provenance}
    path=edit/'result-reviewed.json';write(path,result)
    data['editorial_manifest']['entries'].append({'number':task['number'],'result':{'path':str(path),'sha256':runner.book.byte_hash(path)},
        'review_db':str(edit/'review.db'),'origin_work':origin_ref,'task_sha256':task['task_sha256'],
        'provenance_sha256':runner.canonical_hash(provenance)})
    audit={'path':str(edit/'provider/dispatch.db'),'sha256':runner.book.byte_hash(edit/'provider/dispatch.db')}
    data['editorial_manifest']['spend_lineage'].append(audit);repin_editorial(data)
    completed=runner.run(**options,registry=object(),resume=True,target=None,writer_policy=runner.WRITER_V3,
        verified_editorial_results=data['authority'],complete_word_floor=True)
    current=runner.book.load(options['work']/'editorial-adoption-registry.json')['external_audits']
    assert current==previous+[audit]
    local=runner.reserved_usd(options['work'],[task])
    assert completed['reservation_usd']==pytest.approx(data['expected_held']+local+provider.dispatcher.reserved_usd)
    assert all(Path(p).read_bytes()==raw for p,raw in untouched.items())
    assert not (directory/'word-floor-execution-policy.json').exists()


def count_omission_guard(old, new, parent, number, path, monkeypatch):
    """Pin a synthetic independent exact-omission guard; never use production inputs."""
    prefix = "'" + old['new_sutra'] + "' हे "
    guard = {'gate': 'REQUIRED_MECHANICAL_CORRECTION_CONFIRMED', 'number': number,
        'input': {'result_path': parent['path'], 'result_file_sha256': parent['sha256'],
                  'draft_canonical_sha256': runner.canonical_hash(old)},
        'predicted_output': {'draft_canonical_sha256': runner.canonical_hash(new)},
        'operation': {'kind': 'single_exact_count_modifier_omission', 'field': 'draft.grammar_mr',
            'deleted_exact_text': 'तीन पदांचे ', 'prefix_replacement_count': 1,
            'old_full_field': old['grammar_mr'], 'new_full_field': new['grammar_mr'],
            'old_exact_prefix': prefix + 'तीन पदांचे छोटे सूत्र आहे.',
            'new_exact_prefix': prefix + 'छोटे सूत्र आहे.'}}
    write(path, guard)
    pointer = {'path': str(path), 'sha256': runner.book.byte_hash(path)}
    monkeypatch.setattr(runner, 'COUNT_OMISSION_GUARD_SHA256', pointer['sha256'])
    return pointer


@pytest.fixture
def count_omission_proof(tmp_path, monkeypatch):
    """Build only minimal synthetic saved-request/raw records for the narrow predicate."""
    old = {'new_sutra': 'नियतसमये साधनाभ्यासः', 'number': 13,
        'grammar_mr': "'नियतसमये साधनाभ्यासः' हे तीन पदांचे छोटे सूत्र आहे. उर्वरित व्याकरण जसे आहे तसे.",
        'translation_mr': 'ठरलेल्या वेळी सराव करावा', 'summary_mr': 'अपरिवर्तित सारांश'}
    new = deepcopy(old); new['grammar_mr'] = old['grammar_mr'].replace('तीन पदांचे ', '', 1)
    directory = tmp_path/'original'/'entry'; directory.mkdir(parents=True)
    original = directory/'result.json'; write(original, {'draft': old})
    parent = {'path': str(original), 'sha256': runner.book.byte_hash(original)}
    task = {'number': 13, 'task_sha256': 'b'*64, 'composition_binding': {'source': 'c'*64},
            'proposal': {'proposed_sutra': old['new_sutra']}}
    write(directory.parent/'run-manifest.json', {'binding': {'protocol': 'a'*64}})
    with sqlite3.connect(directory/'council.db') as db:
        db.execute('CREATE TABLE research_stages(number,stage,speaker,request_hash,response_json)')
        db.execute('CREATE TABLE research_attempts(number,stage,speaker,state,request_hash,response_json)')
        response = json.dumps(old, ensure_ascii=False)
        db.execute('INSERT INTO research_stages VALUES (13,?,?,?,?)', ('composition','sutrakar','d'*64,response))
        db.execute('INSERT INTO research_attempts VALUES (13,?,?,?,?,?)', ('composition','sutrakar','COMPLETE','d'*64,response))
    provider = directory/'provider'; (provider/'raw').mkdir(parents=True)
    raw = provider/'raw'/'slot.txt'; write(raw, {'original': 'response'})
    source_hash = runner._hash({'protocol': 'a'*64, **task['composition_binding'],
        'composition_binding': runner.canonical_hash(task['composition_binding']), 'task': task['task_sha256']})
    with sqlite3.connect(provider/'boundary.db') as db:
        db.execute('CREATE TABLE calls(slot,status,request_sha256,source_sha256,raw_sha256,result_json)')
        db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?)', ('slot','SUCCESS','e'*64,source_hash,
                   runner.book.byte_hash(raw),json.dumps({'original': 'response'})))
    write(directory/'initial-formula-binding.json', {'composition_binding': task['composition_binding'],
        'canonical_formula': old['new_sutra'], 'proposal_sha256': runner.canonical_hash(task['proposal']),
        'provider_slot': 'slot', 'provider_request_sha256': 'e'*64,
        'original_raw_sha256': runner.book.byte_hash(raw),
        'original_response_sha256': runner.canonical_hash({'original': 'response'})})
    pointer = count_omission_guard(old,new,parent,13,tmp_path/'guard.json',monkeypatch)
    provenance = {'mechanical_count_omission_guard': pointer, 'patches': [
        {'field': 'grammar_mr', 'before': old['grammar_mr'], 'after': new['grammar_mr']}]}
    return old,new,provenance,task,directory,parent


def test_count_omission_exact_predicate_and_documented_patch(count_omission_proof, tmp_path):
    """Only the exact false count modifier is omitted; current writer proof is audited."""
    old,new,provenance,task,directory,parent = count_omission_proof
    proof = runner._count_claim_omission(old,new,provenance,tmp_path,task,directory,parent)
    runner._documented_editorial(old,new,provenance,count_omission_verified=True)
    assert proof['composition_request_sha256'] == 'd'*64
    assert proof['writer_request_sha256'] == 'e'*64
    assert {k:v for k,v in old.items() if k != 'grammar_mr'} == {k:v for k,v in new.items() if k != 'grammar_mr'}
    with pytest.raises(ValueError):
        runner._documented_editorial(old,new,provenance)


@pytest.mark.parametrize('damage', ['semantic_grammar','translation','formula','summary','prefix',
    'missing_guard','guard_sha','writer_raw','composition_request','old_draft'])
def test_count_omission_cannot_authorize_other_edits(count_omission_proof,tmp_path,damage):
    """No semantic rewrite, other draft field, false prefix or stale request/raw is allowed."""
    old,new,provenance,task,directory,parent = count_omission_proof
    if damage == 'semantic_grammar': new['grammar_mr'] += ' अर्थ बदलला.'
    elif damage == 'translation': new['translation_mr'] += ' बदल'
    elif damage == 'formula': new['new_sutra'] = 'अन्यं सूत्रम्'
    elif damage == 'summary': new['summary_mr'] += ' बदल'
    elif damage == 'prefix': old['grammar_mr'] = 'अन्य प्रस्तावना. ' + old['grammar_mr']
    elif damage == 'missing_guard': provenance.pop('mechanical_count_omission_guard')
    elif damage == 'guard_sha': provenance['mechanical_count_omission_guard']['sha256'] = '0'*64
    elif damage == 'writer_raw': (directory/'provider/raw/slot.txt').write_bytes(b'{}')
    elif damage == 'old_draft': old['summary_mr'] += ' बदल'
    else:
        with sqlite3.connect(directory/'council.db') as db:
            db.execute("UPDATE research_stages SET request_hash='changed'")
    with pytest.raises(ValueError):
        runner._count_claim_omission(old,new,provenance,tmp_path,task,directory,parent)


@pytest.mark.parametrize('fresh', [True, False])
def test_count_omission_ready_same_root_requires_fresh_complete_fifth(tmp_path,monkeypatch,fresh):
    """Adopt only a freshly reviewed exact omission; keep original READY/raw/history unchanged."""
    respond = CompositionRegistry.respond
    def wrong_count(self,voice,payload):
        """Supply a synthetic wrong count in the original complete writer response only."""
        value = respond(self,voice,payload)
        value['grammar_mr'] = "'" + payload['proposal']['proposed_sutra'] + "' हे तीन पदांचे छोटे सूत्र आहे. उर्वरित अर्थ कायम."
        return value
    monkeypatch.setattr(CompositionRegistry,'respond',wrong_count)
    data = editorial_fixture(tmp_path,monkeypatch)
    task = runner.validate_task(data['tasks'][0],tmp_path,set(),set())
    _,directory,old,original,parent = runner._origin(task,{
        'path':str(data['origin']),'manifest_sha256':runner.book.byte_hash(data['origin']/'run-manifest.json')})
    untouched = {str(p):p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    draft = deepcopy(old); draft['grammar_mr'] = old['grammar_mr'].replace('तीन पदांचे ','',1)
    pointer = count_omission_guard(old,draft,parent,task['number'],tmp_path/'count-guard.json',monkeypatch)
    provenance = {'parent_result':parent,'old_draft_sha256':runner.canonical_hash(old),
        'new_draft_sha256':runner.canonical_hash(draft),'mechanical_count_omission_guard':pointer,
        'patches':[{'field':'grammar_mr','before':old['grammar_mr'],'after':draft['grammar_mr']}]}
    edit = tmp_path/'count-edit'; provider = runner.SourceFirstProvider(edit/'provider',CompositionRegistry(),
        source_hashes={'count-edit':'f'*64},max_usd=.25,max_calls=1,claude_cap_usd=.1)
    review = (runner.IndependentReviewer(edit/'review.db',runner.book.WritingCalls(provider,edit).validator)
              .review(draft,task['effective_sources'],[])) if fresh else original['review']
    result = deepcopy(original); result.update(draft=draft,review=review,editorial_provenance=provenance,
        assessment=runner.assess_source_first_entry(draft,task['effective_sources'],
        runner._effective_prior(task,[]),runner.book.load(data['options']['forbidden_path']),set()))
    result['review_history'].append({'stage':'editorial','review':review,'draft_sha256':runner.canonical_hash(draft)})
    path = edit/'result-reviewed.json'; write(path,result)
    item = data['editorial_manifest']['entries'][0]
    item.update(result={'path':str(path),'sha256':runner.book.byte_hash(path)},review_db=str(edit/'review.db'),
                provenance_sha256=runner.canonical_hash(provenance))
    data['editorial_manifest']['spend_lineage'] = ([{'path':str(edit/'provider/dispatch.db'),
        'sha256':runner.book.byte_hash(edit/'provider/dispatch.db')}] if fresh else [])
    repin_editorial(data)
    if not fresh:
        with pytest.raises(ValueError,match='review key/database'):
            runner.run(**data['options'],registry=object(),resume=True,verified_editorial_results=data['authority'])
    else:
        def no_provider(*args,**kwargs):
            """Editorial adoption must not construct or rerun any paid adapter."""
            pytest.fail('No calls during adoption')
        monkeypatch.setattr(runner,'SourceFirstProvider',no_provider)
        out = runner.run(**data['options'],registry=object(),resume=True,verified_editorial_results=data['authority'])
        assert out['ready'][0]['draft'] == draft
        assert out['ready'][0]['authority']['mechanical_count_omission']['guard'] == pointer
    assert all(Path(path).read_bytes()==raw for path,raw in untouched.items())

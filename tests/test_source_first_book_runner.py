"""Fake-only integration: actual council, provider boundary, reviewer and assessor.

Synthetic drafts exercise structure, not Sanskrit/Marathi quality or case truth.
No credentials, SDKs, network, paid inference, exports or old checkpoints.
"""
from collections import Counter
from copy import deepcopy
import json
import sqlite3
import threading
import time
from types import SimpleNamespace

import pytest

from scripts import run_source_first_book as runner
from src.orchestration import independent_review as review
from src.orchestration.source_first_provider import SourceFirstStopped
from tests.test_source_first_book_plan import fixture, card, book
from tests.test_source_first_provider import FakeAdapter
from tests.test_independent_review_v2 import answer, source_check, reference_answer


def prepared(count=2):
    """Use Jason's real preparation module with explicitly curated synthetic cards."""
    args = fixture()
    args['ordered_selection_cards'] = [card()]
    for number in range(2, count + 1):
        # Explicit synthetic cases are unique to these test-only plan entries.
        ids = []
        for kind in ('positive', 'caution'):
            case = deepcopy(args['case_pool']['cases'][0 if kind == 'positive' else 1])
            case.update(case_id=f'{kind}-{number}', canonical_case_id=f'{kind}-{number}',
                        entity=f'Synthetic {kind} {number}')
            case['entity_identity'] = {'normalized_entity_key': f'{kind}{number}',
                                      'deduplication_keys': [f'{kind}{number}'],
                                      'recorded_aliases_and_related_labels': []}
            args['case_pool']['cases'].append(case)
            check = deepcopy(args['verification_overlay']['fact_verifications'][0])
            check.update(case_id=case['case_id'], case_pool_record_sha256=book.digest(case))
            args['verification_overlay']['fact_verifications'].append(check)
            ids.append(case['case_id'])
        args['ordered_selection_cards'].append(card(pair=f'N{number + 1:03d}-S002',
            suffix=str(number), stage='practice', positive=ids[0], caution=ids[1]))
    args['case_pool']['case_count'] = len(args['case_pool']['cases'])
    return book.prepare_book_plan(**args)


class Registry:
    """Five exact frozen fake roles with observable real dispatch calls."""

    def __init__(self, rejected=(), missing_support=False, draft_defect=None, validator_fault=None):
        """Configure bounded synthetic responses and failures; never load a key."""
        self.calls, self.active, self.maximum_active = [], 0, 0
        self.lock = threading.Lock()
        self.rejected = rejected
        self.missing_support, self.draft_defect = missing_support, draft_defect
        self.validator_fault = validator_fault
        self.adapters = {role: FakeAdapter(voice) for voice, (role, _) in runner.MODELS.items()}
        for voice, (role, _) in runner.MODELS.items():
            adapter = self.adapters[role]
            adapter.effort = 'original'
            adapter.generate = lambda prompt, system_prompt, v=voice, a=adapter: self.generate(v, a, prompt, system_prompt)

    def get_adapter(self, role):
        """Resolve the fixed offline role; missing roles fail immediately."""
        return self.adapters[role]

    def generate(self, voice, adapter, prompt, system):
        """Observe serialized transport and return realistic dispatch metadata."""
        with self.lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
        try:
            time.sleep(.001)
            self.calls.append({'voice': voice, 'prompt': prompt, 'system': system,
                               'tokens': adapter.max_tokens, 'effort': adapter.effort,
                               'timeout': adapter.timeout_seconds})
            if voice == 'validator':
                if self.validator_fault == 'credit':
                    raise RuntimeError('synthetic-secret-not-for-logs')
                assert system == review.SYSTEM
                assert prompt.startswith(review.CONTRACT + '\nEVIDENCE\n')
                payload = json.loads(prompt.split('\nEVIDENCE\n', 1)[1])
                assert prompt == review.CONTRACT + '\nEVIDENCE\n' + json.dumps(payload, ensure_ascii=False, sort_keys=True)
                assert 'discussion' not in payload and 'proposal' not in payload
                refs = {r['id']: r for r in payload['canonical_sources']['references']}
                checks = [source_check(field=p['field'], source_id=p['source_id'],
                          application=p['current_claim'], source_quote=refs[p['source_id']]['original_text'])
                          for p in payload['00_review_checks']['source_claim_pairs']]
                value = reference_answer(answer(source_checks=checks), payload)
            else:
                envelope = json.loads(prompt)
                value = self.respond(voice, envelope['input'])
            return SimpleNamespace(content=json.dumps(value, ensure_ascii=False),
                model_id=adapter.model_id, provider=adapter.provider_name,
                was_truncated=voice == 'validator' and self.validator_fault == 'truncated',
                finish_reason='stop', usage=SimpleNamespace(input_tokens=10, output_tokens=10,
                                                           total_tokens=20, actual_cost_usd=None))
        finally:
            with self.lock:
                self.active -= 1

    def respond(self, voice, payload):
        """Actually consume peer challenges; select or reject only after all rounds."""
        stage = payload['stage']
        numbers = payload.get('entry_numbers', [payload['number']])
        if stage == 'position':
            return {'positions': {str(n): {'thesis': f'{voice} source position {n}'} for n in numbers}}
        if stage == 'challenge':
            positions = payload['discussion']['position']
            assert set(positions) == set(runner.VOICES)
            return {'challenges': {peer: {str(n): f"Question about {positions[peer]['positions'][str(n)]['thesis']}"
                    for n in numbers} for peer in runner.VOICES if peer != voice}}
        if stage == 'reply':
            challenges = payload['discussion']['challenge']
            assert set(challenges) == set(runner.VOICES)
            return {'answers': {peer: {str(n): 'Evidence answer to ' + challenges[peer]['challenges'][voice][str(n)]
                    for n in numbers} for peer in runner.VOICES if peer != voice}}
        if stage == 'proposal':
            assert set(payload['discussion']) == {'position', 'challenge', 'reply'}
            rows = []
            for n in numbers:
                if n in self.rejected:
                    rows.append({'number': n, 'decision': 'REJECT',
                                 'rejection_reason': 'या उदाहरणातून प्रस्तावित नियमाला पुरेसा विशिष्ट आधार मिळत नाही'})
                else:
                    refs = [r['id'] for r in payload['sources'][str(n)]['references']]
                    rows.append({'number': n, 'decision': 'ACCEPT', 'proposed_sutra': 'उद्यमेन विवेकः',
                                 'derivation': 'Synthetic test derivation only',
                                 'selected_source_ids': refs[:2] if self.missing_support else refs})
            return {'proposals': rows}
        if stage == 'peer_review':
            return {'reviews': [{'number': n, 'verdict': 'PASS', 'issues': []} for n in numbers]}
        if stage.startswith('composition'):
            assert payload['number'] not in self.rejected
            packet = payload['sources']
            refs = [r['id'] for r in packet['references']]
            if self.draft_defect == 'missing_source':
                refs = refs[1:]
            cases = [c['case_id'] for c in packet['examples']]
            if self.draft_defect == 'wrong_case':
                cases.reverse()
            return {'new_sutra': ['उद्यमेन विवेकः', 'प्रमाणेन निर्णयः', 'निष्ठया सेवा'][payload['number'] - 1],
                'title_mr': 'चाचणी', 'grammar_mr': 'चाचणीपुरते व्याकरण', 'translation_mr': 'चाचणीपुरता अर्थ',
                'exposition': ['विचार ' * 510], 'references': refs, 'case_ids': cases,
                'comparative_mr': [{'source_id': r, 'explanation_mr': 'आधुनिक उपयोगाची चाचणी'} for r in refs],
                'dos_mr': ['करावे'] * 3, 'donts_mr': ['टाळावे'] * 3,
                'application_mr': 'चाचणीपुरती कृती', 'action_mr': f"कृती {payload['number']}",
                'summary_mr': f"सारांश {payload['number']}"}
        raise AssertionError(stage)


@pytest.fixture(autouse=True)
def no_credentials(monkeypatch):
    """Every test trips on a live credential loader or real registry constructor."""
    def forbidden(*args, **kwargs):
        pytest.fail('Live credential/provider access forbidden')
    monkeypatch.setattr('scripts.run_research_book.load_project_credentials', forbidden)
    monkeypatch.setattr('src.providers.registry.ProviderRegistry', forbidden)


@pytest.fixture
def options(tmp_path, monkeypatch):
    """Write only temporary synthetic inputs and a trusted test-gate fixture.

    The calibration checker is stubbed here; its unchanged real implementation
    and independent calibration regressions are run separately at handoff.
    """
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    plan = inputs / 'prepared.json'
    runner.save(plan, prepared(3))
    forbidden = inputs / 'forbidden.json'
    runner.save(forbidden, ['चाचणीपुरती मूळ सूत्रनोंद'])
    gate = inputs / 'offline-gate.json'
    runner.save(gate, {'status': 'PASS', 'paid_calls': 0, 'code_sha256': runner.code_bindings(),
        'tests': [{'path': name, 'passed': 1, 'failed': 0, 'errors': 0} for name in runner.REQUIRED_TESTS]})
    monkeypatch.setattr(runner, 'require_validator_calibration', lambda path: {'status': 'PASS', 'fixture': 'synthetic'})
    return dict(plan_path=plan, plan_sha256=runner.byte_hash(plan), forbidden_path=forbidden,
                calibration_dir=inputs / 'calibration', offline_gate=gate,
                work=tmp_path / 'new-book', budget=20., claude_cap=15., max_calls=200)


def stages(registry):
    """Return observed council stages, excluding the separately raw validator."""
    return Counter(json.loads(c['prompt'])['input']['stage'] for c in registry.calls if c['voice'] != 'validator')


@pytest.mark.parametrize('mode,tokens', [('formula', 6000), ('exposition', 6000), ('full', 18000)])
def test_writer_repair_reserves_exact_limit_and_reuses_success(tmp_path, monkeypatch, mode, tokens):
    """Real dispatch reserves 6k for narrow repairs, 18k for full writing; all use medium effort."""
    item = prepared(1)['entries'][0]
    fake = Registry()
    payload = {'stage': 'composition_v2_1', 'number': 1, 'speaker': 'sutrakar',
               'brief': runner.council_brief(item), 'sources': item['source_packet'], 'discussion': {}}
    draft = runner.complete_entry(fake.respond('sutrakar', payload), payload)
    payload['draft'] = deepcopy(draft)
    if mode == 'formula':
        payload.update(assessment={'status': 'PASS', 'issues': []},
                       review={'verdict': 'REVIEW_REQUIRED', 'issues': [{'field': 'grammar_mr'}]})
        response = {'patch': {key: draft[key] for key in ('new_sutra', 'grammar_mr', 'translation_mr')}}
    elif mode == 'exposition':
        payload['draft']['exposition'] = ['विचार ' * 450]
        payload.update(assessment={'status': 'NEEDS_REVISION', 'issues': [
            'exposition has 450 Devanagari word tokens; at least 500 required']},
            review={'verdict': 'PASS', 'issues': []})
        response = {'additional_paragraph_mr': 'चाचणी ' * 160}
    else:
        payload.update(assessment={'status': 'NEEDS_REVISION', 'issues': ['Broader repair']},
                       review={'verdict': 'REVIEW_REQUIRED', 'issues': [{'field': 'exposition'}]})
        response = deepcopy(draft)
    monkeypatch.setattr(fake, 'respond', lambda voice, request: deepcopy(response))
    provider = runner.SourceFirstProvider(tmp_path / 'provider', fake,
        source_hashes={'plan': 'a' * 64}, max_usd=1., max_calls=5, claude_cap_usd=1.)
    calls = runner.WritingCalls(provider, tmp_path)
    result = calls.voice('sutrakar', payload)
    assert result['examples'] == item['source_packet']['examples']
    assert result['references'] == draft['references']
    if mode == 'exposition':
        assert result['exposition'] == [response['additional_paragraph_mr'], payload['draft']['exposition'][0]]
    else:
        assert result['exposition'] == draft['exposition']
    assert len(fake.calls) == 1 and fake.calls[0]['tokens'] == tokens
    assert fake.calls[0]['effort'] == 'medium'
    rate = runner.RATES[f"{runner.PROVIDERS['sutrakar']}:{runner.MODELS['sutrakar'][1]}"]
    expected = (10 * rate['input'] + tokens * rate['output']) / 1_000_000
    with sqlite3.connect(tmp_path / 'provider' / 'dispatch.db') as db:
        reservation, record = db.execute('SELECT reservation_usd,record_json FROM council_dispatch_audit').fetchone()
    assert json.loads(record)['max_output_tokens'] == tokens
    assert reservation == pytest.approx(expected)
    assert provider.spend_guard.reserved_usd == pytest.approx(expected)
    assert calls.voice('sutrakar', payload) == result
    assert len(fake.calls) == 1 and provider.dispatcher.calls == 1
    assert provider.spend_guard.reserved_usd == pytest.approx(expected)


def test_pilot_resume_reuses_all_successes_and_keeps_rejection(options):
    """Real four-voice discussion, accepted composition, raw review and durable resume."""
    fake = Registry(rejected=(2,))
    before = runner.byte_hash(options['plan_path'])
    first = runner.run(**options, registry=fake, target=1)
    assert first['completed'] == [1] and first['status'] == 'READY_FOR_AUTHOR_REVIEW'
    assert stages(fake) == {'position': 4, 'challenge': 4, 'reply': 4, 'proposal': 1, 'peer_review': 3, 'composition': 1}
    count = len(fake.calls)
    pilot = (options['work'] / 'entry-001.json').read_bytes()
    second = runner.run(**options, registry=fake, resume=True)
    assert second['completed'] == [1, 3] and second['rejected'] == [2]
    assert len(fake.calls) - count == 18  # 16 batch rounds + composition + independent review
    assert (options['work'] / 'entry-001.json').read_bytes() == pilot
    decline = runner.load(options['work'] / 'entry-002.json')
    assert decline['status'] == 'REJECTED' and 'proposed_sutra' not in decline['proposal']
    saved = runner.load(options['work'] / 'entry-003.json')
    plan = runner.load(options['plan_path'])
    assert saved['draft']['examples'] == plan['entries'][2]['source_packet']['examples']
    assert saved['assessment']['status'] == 'PASS'
    assert saved['review']['outcome'] == 'READY'
    from src.doc_export.research_book import _validate
    drafts = [runner.load(options['work'] / f'entry-{n:03d}.json')['draft'] for n in (1, 3)]
    assert [d['chapter'] for d in drafts] == [1, 2]
    assert all(type(d['chapter']) is int for d in drafts)
    references = {r['id']: r for item in plan['entries'] for r in item['source_packet']['references']}
    chapters = [{'number': n, 'title_mr': 'चाचणी अध्याय'} for n in (1, 2)]
    assert _validate(drafts, chapters, references, [])[0] == {1: 'चाचणी अध्याय', 2: 'चाचणी अध्याय'}
    assert fake.maximum_active == 1
    for call in fake.calls:
        assert call['timeout'] == 240
        if call['voice'] == 'validator':
            assert call['tokens'] == 3000
        else:
            payload = json.loads(call['prompt'])['input']
            if payload['stage'].startswith('composition'):
                assert call['tokens'] == 18000 and call['effort'] == 'medium'
            elif call['voice'] in ('researcher', 'sutrakar'):
                assert call['effort'] == 'low'
    count = len(fake.calls)
    again = runner.run(**options, registry=fake, resume=True)
    assert len(fake.calls) == count and again == second
    assert runner.byte_hash(options['plan_path']) == before


def test_partial_batch_target_preserves_full_batch_request(options):
    """Target two must discuss all of the stable second batch, including entry three."""
    fake = Registry(rejected=(2,))
    runner.run(**options, registry=fake, target=2)
    count = len(fake.calls)
    runner.run(**options, registry=fake, resume=True)
    assert len(fake.calls) - count == 2  # compose/review third, no repeated discussion


def test_stable_partition_has_singleton_then_tens():
    """Batch identities come from the full plan, never from target slicing."""
    values = list(range(26))
    assert runner.planned_batches(values) == [values[:1], values[1:11], values[11:21], values[21:]]


@pytest.mark.parametrize('status', ['MATCH', 'QUALIFIED'])
def test_bound_fresh_fact_without_legacy_boolean_is_accepted_unchanged(status):
    """Fresh proof may omit the legacy boolean; neither planner nor runner invents it."""
    args = fixture()
    for check in args['verification_overlay']['fact_verifications']:
        check['status'] = status
        check.pop('existing_marathi_material_fact_contradiction_found')
    plan = book.prepare_book_plan(**args)
    before = deepcopy(plan)
    runner.validate_plan(plan)
    assert plan == before
    for assignment in plan['entries'][0]['case_assignments']:
        assert 'existing_marathi_material_fact_contradiction_found' not in assignment['verification']


@pytest.mark.parametrize('status', ['MATCH', 'QUALIFIED'])
def test_explicit_case_contradiction_is_held_without_changing_proof(status):
    """An explicit contradiction blocks even otherwise bound MATCH/QUALIFIED proof."""
    plan = prepared(1)
    item = plan['entries'][0]
    for assignments in (item['case_assignments'], item['source_packet']['case_assignments']):
        check = assignments[0]['verification']
        check.update(status=status, existing_marathi_material_fact_contradiction_found=True)
    before = deepcopy(plan)
    with pytest.raises(ValueError, match='Canonical case/fact verification drift or HOLD'):
        runner.validate_plan(plan)
    assert plan == before


def test_journey_maps_to_integer_contiguous_export_chapters_without_losing_label():
    """Growth/people/society share chapter three; original journey labels survive."""
    labels = ['opening', 'practice', 'growth', 'people', 'society', 'closure']
    items = [{'number': n, 'brief': {'number': n, 'journey_stage': label}}
             for n, label in enumerate(labels, 1)]
    before = deepcopy(items)
    briefs = [runner.council_brief(item) for item in items]
    assert [b['chapter'] for b in briefs] == [1, 2, 3, 3, 3, 4]
    assert all(type(b['chapter']) is int for b in briefs)
    assert [b['journey_stage'] for b in briefs] == labels
    assert items == before


def test_missing_supplementary_proposal_never_composes(options):
    """The source-support gate runs after discussion but before long writer calls."""
    fake = Registry(missing_support=True)
    with pytest.raises(SourceFirstStopped):
        runner.run(**options, registry=fake, target=1)
    assert not any(k.startswith('composition') for k in stages(fake))
    assert all(c['voice'] != 'validator' for c in fake.calls)


@pytest.mark.parametrize('defect', ['missing_source', 'wrong_case'])
def test_composition_cannot_drop_source_or_replace_case(options, defect):
    """Structural faithfulness is required even if the fake reviewer says READY."""
    fake = Registry(draft_defect=defect)
    if defect == 'wrong_case':
        with pytest.raises(SourceFirstStopped):
            runner.run(**options, registry=fake, target=1)
    else:
        result = runner.run(**options, registry=fake, target=1)
        assert result['status'] == 'QUALITY_STOP' and result['completed'] == []
        entry = runner.load(options['work'] / 'entry-001.json')
        assert 'Both canonical Narada/Shandilya references must remain in the composition' in entry['assessment']['issues']


@pytest.mark.parametrize('fault', ['credit', 'truncated'])
def test_failed_independent_review_stops_without_retries(options, fault):
    """Raw partials persist; no rewritten chapter or paid reviewer retry on resume."""
    fake = Registry(validator_fault=fault)
    with pytest.raises(SourceFirstStopped):
        runner.run(**options, registry=fake, target=1)
    count = len(fake.calls)
    with pytest.raises(SourceFirstStopped):
        runner.run(**options, registry=fake, resume=True, target=1)
    assert len(fake.calls) == count
    assert sum(c['voice'] == 'validator' for c in fake.calls) == 1
    assert stages(fake)['composition'] == 1
    with sqlite3.connect(options['work'] / 'independent_review_v2.db') as db:
        row = db.execute('SELECT state,error FROM independent_reviews_v2').fetchone()
        assert row[0] == 'FAILED' and 'synthetic-secret' not in row[1]
    if fault == 'truncated':
        assert list((options['work'] / 'review-raw').glob('*.txt'))


@pytest.mark.parametrize('change', ['code', 'calibration', 'plan', 'case', 'source'])
def test_preflight_failures_precede_live_factory(options, monkeypatch, change):
    """Exact-code/calibration/frozen evidence gates cannot load credentials on failure."""
    calls = []
    monkeypatch.setattr(runner, 'create_live_provider', lambda *a, **k: calls.append(k))
    if change == 'code':
        gate = runner.load(options['offline_gate'])
        gate['code_sha256']['scripts/run_source_first_book.py'] = '0' * 64
        runner.save(options['offline_gate'], gate)
    elif change == 'calibration':
        def failed(path):
            raise ValueError('stale calibration')
        monkeypatch.setattr(runner, 'require_validator_calibration', failed)
    else:
        plan = runner.load(options['plan_path'])
        if change == 'case':
            plan['entries'][0]['source_packet']['examples'][0]['text_mr'] = 'changed fact'
        elif change == 'source':
            plan['entries'][0]['source_packet']['references'][0]['original_text'] = 'changed source'
        else:
            plan['status'] = 'changed'
        runner.save(options['plan_path'], plan)
        if change != 'plan':
            options['plan_sha256'] = runner.byte_hash(options['plan_path'])
    with pytest.raises(ValueError):
        runner.run(**options, live=True, credentials_dir='never-read')
    assert calls == [] and not options['work'].exists()


def test_no_live_flag_only_preflights_and_resume_binding_is_frozen(options):
    """Offline CLI-equivalent preflight writes nothing; changed targets alone are allowed."""
    assert runner.run(**options)['status'] == 'OFFLINE_PREFLIGHT_PASS'
    assert not options['work'].exists()
    fake = Registry()
    runner.run(**options, registry=fake, target=1)
    changed = dict(options, budget=21.)
    count = len(fake.calls)
    with pytest.raises(ValueError, match='Resume'):
        runner.run(**changed, registry=fake, resume=True)
    assert len(fake.calls) == count


def test_legacy_directory_rejected_before_factory(options, monkeypatch):
    """No run can write under the old 42-entry checkpoint tree."""
    from scripts.run_research_book import WORK
    options['work'] = WORK / 'new-child'
    with pytest.raises(ValueError, match='Legacy'):
        runner.run(**options, live=True, credentials_dir='never-read')


def test_new_folder_required_and_unassigned_plan_fails(options):
    """An existing folder or an unresolved case slot cannot silently become a run."""
    options['work'].mkdir()
    with pytest.raises(ValueError, match='Fresh'):
        runner.run(**options)
    plan = runner.load(options['plan_path'])
    plan['entries'][0]['council_ready'] = False
    with pytest.raises(ValueError, match='UNASSIGNED'):
        runner.validate_plan(plan)


def synchronize_test_plan(plan):
    """Repin redundant synthetic views so negative probes reach the intended gate."""
    for item in plan['entries']:
        packet = item['source_packet']
        packet['case_assignments'] = deepcopy(item['case_assignments'])
        packet['examples'] = [{k: a['canonical_case'][k] for k in runner.CASE_FIELDS}
                              for a in item['case_assignments']]
        provenance = packet['selection_provenance']
        provenance['selection_card_sha256'] = book.digest(provenance['selection_card'])
        item['brief']['selection_provenance'] = deepcopy(provenance)
    plan['selection_cards_sha256'] = book.digest([
        e['source_packet']['selection_provenance']['selection_card'] for e in plan['entries']])
    plan['council_payload'] = {
        'briefs': [deepcopy(e['brief']) for e in plan['entries']],
        'sources_by_entry': {str(e['number']): deepcopy(e['source_packet']) for e in plan['entries']}}


def rebind_test_case(assignment):
    """Keep actual fact bytes bound after a synthetic identity/status change."""
    case = assignment['canonical_case']
    assignment['verification']['case_pool_record_sha256'] = book.digest(case)
    if assignment['identity_verification'] is not None:
        assignment['identity_verification']['case_pool_record_sha256'] = book.digest(case)


def reject_before_provider(options, monkeypatch, plan, message):
    """Supply newly frozen bytes and require rejection before setup, without edits."""
    synchronize_test_plan(plan)
    runner.save(options['plan_path'], plan)
    settings = {**options, 'plan_sha256': runner.byte_hash(options['plan_path'])}
    before, setup = deepcopy(plan), []
    monkeypatch.setattr(runner, 'create_live_provider', lambda *a, **k: setup.append(k))
    with pytest.raises(ValueError, match=message):
        runner.run(**settings, live=True, credentials_dir='never-read')
    assert not setup and not options['work'].exists()
    assert runner.load(options['plan_path']) == before


@pytest.mark.parametrize('defect,message', [
    ('identity_hold', 'identity HOLD'), ('canonical_hold', 'identity HOLD'),
    ('flag_hold', 'identity HOLD'), ('identity_hash', 'identity verification owner/hash'),
    ('identity_owner', 'identity verification owner/hash'),
    ('forged_reservation', 'reservations differ'), ('missing_reservation', 'reservations differ'),
    ('shared_entity', 'Shared canonical identity'), ('shared_alias', 'Shared canonical identity'),
    ('shared_verified_label', 'Shared canonical identity'),
    ('recorded_conflict', 'conflicting cross-case'), ('relationship_hash', 'relationship binding'),
])
def test_bkr01_identity_holds_reservations_and_conflicts_block_setup(options, monkeypatch, defect, message):
    """Reproduce BKR-01 with fully rebound facts; no provider or input repair allowed."""
    plan = prepared(2)
    first, second = (e['case_assignments'][0] for e in plan['entries'])
    if defect.startswith('identity_'):
        first['identity_verification'] = {'case_id': first['case_id'], 'status': 'MATCH',
            'case_pool_record_sha256': book.digest(first['canonical_case']), 'verified_relationships': []}
        if defect == 'identity_hold':
            first['identity_verification']['status'] = 'HOLD'
        elif defect == 'identity_hash':
            first['identity_verification']['case_pool_record_sha256'] = '0' * 64
        else:
            first['identity_verification']['case_id'] = second['case_id']
    elif defect in ('canonical_hold', 'flag_hold'):
        if defect == 'canonical_hold':
            first['canonical_case']['new_book_status'] = 'HOLD_TEST'
        else:
            first['canonical_case']['flags'].append('HOLD_TEST')
        rebind_test_case(first)
    elif defect in ('forged_reservation', 'missing_reservation'):
        if defect == 'forged_reservation':
            for assignment in (first, second):
                assignment['identity_reservations'] = sorted(assignment['identity_reservations'] + ['sharedfixture'])
        else:
            first['identity_reservations'].pop()
    elif defect.startswith('shared_'):
        for assignment, label in zip((first, second), ('Shared Fixture', ' shared-fixture ')):
            if defect == 'shared_entity':
                # Retain the old synthetic name as recorded proof, so this probe
                # tests the shared normalized entity rather than a stale key list.
                assignment['canonical_case']['entity_identity']['recorded_aliases_and_related_labels'].append(
                    assignment['canonical_case']['entity'])
                assignment['canonical_case']['entity'] = label
            elif defect == 'shared_alias':
                assignment['canonical_case']['entity_identity']['recorded_aliases_and_related_labels'].append(label)
            else:
                assignment['identity_verification'] = {'case_id': assignment['case_id'], 'status': 'QUALIFIED',
                    'case_pool_record_sha256': book.digest(assignment['canonical_case']),
                    'verified_relationships': [{'label': label}]}
            rebind_test_case(assignment)
            assignment['identity_reservations'] = sorted(assignment['identity_reservations'] + ['sharedfixture'])
    else:
        relation = {'case_ids': [first['case_id'], second['case_id']],
                    'case_record_bindings': {a['case_id']: book.digest(a['canonical_case']) for a in (first, second)},
                    'relationship': 'Synthetic recorded conflict', 'status': 'QUALIFIED'}
        if defect == 'relationship_hash':
            relation['case_record_bindings'][second['case_id']] = '0' * 64
        # Even evidence recorded on only one selected member cannot hide a conflict.
        first['relationship_provenance'] = [relation]
    reject_before_provider(options, monkeypatch, plan, message)


def test_bkr01_external_relationship_and_qualified_identity_proof_remain_exact():
    """Unassigned relationship members need no invented records; preserve limited proof."""
    args = fixture()
    first, external = args['case_pool']['cases'][0], args['case_pool']['cases'][2]
    args['verification_overlay']['identity_verifications'] = [{
        'case_id': first['case_id'], 'status': 'QUALIFIED',
        'case_pool_record_sha256': book.digest(first),
        'verified_relationships': [{'label': 'Recorded Related Label'}], 'limitations_mr': 'चाचणीपुरती मर्यादा'}]
    args['verification_overlay']['cross_case_relationships'] = [{
        'case_ids': [first['case_id'], external['case_id']], 'person': 'Recorded Shared Person',
        'case_record_bindings': {c['case_id']: book.digest(c) for c in (first, external)},
        'status': 'QUALIFIED', 'relationship': 'Synthetic recorded relationship'}]
    for check in args['verification_overlay']['fact_verifications']:
        check.pop('existing_marathi_material_fact_contradiction_found')
    plan = book.prepare_book_plan(**args)
    before = deepcopy(plan)
    runner.validate_plan(plan)
    assert plan == before


@pytest.mark.parametrize('field', ['topic_mr', 'decision_mr', 'action_mr', 'source_derivation_mr',
                                 'ordering_reason_mr', 'journey_stage', 'pair_reference_ids'])
def test_bkr02_exact_brief_card_drift_blocks_setup(options, monkeypatch, field):
    """A valid frozen hash does not permit execution of a contradictory brief."""
    plan = prepared(2)
    plan['entries'][0]['brief'][field] = (['N3', 'S2'] if field == 'pair_reference_ids'
                                         else 'closure' if field == 'journey_stage' else 'Changed synthetic brief')
    reject_before_provider(options, monkeypatch, plan, 'brief differs from exact selection card')


@pytest.mark.parametrize('labels,message', [
    (['closure', 'opening'], 'reverse the reader journey'),
    (['unknown', 'practice'], 'Unknown reader journey'),
])
def test_bkr02_coherently_repinned_invalid_journey_blocks_setup(options, monkeypatch, labels, message):
    """Reject unknown/backward ranks even with matching cards, briefs and current hashes."""
    plan = prepared(2)
    for item, label in zip(plan['entries'], labels):
        item['brief']['journey_stage'] = label
        item['source_packet']['selection_provenance']['selection_card']['journey_stage'] = label
    reject_before_provider(options, monkeypatch, plan, message)


@pytest.mark.parametrize('label,chapter', [('opening', 1), ('practice', 2), ('growth', 3),
                                          ('people', 3), ('society', 3), ('closure', 4)])
def test_bkr02_all_preparer_journey_labels_pass_unchanged(label, chapter):
    """Every legitimate preparer stage retains its integer export chapter."""
    args = fixture()
    args['ordered_selection_cards'][0]['journey_stage'] = label
    plan = book.prepare_book_plan(**args)
    before = deepcopy(plan)
    runner.validate_plan(plan)
    assert runner.council_brief(plan['entries'][0])['chapter'] == chapter
    assert plan == before


def test_bkr02_equal_middle_journey_ranks_are_not_reordered():
    """Match the preparer's rank rule, including arbitrary order within rank two."""
    plan = prepared(3)
    for item, label in zip(plan['entries'], ('society', 'people', 'growth')):
        item['brief']['journey_stage'] = label
        item['source_packet']['selection_provenance']['selection_card']['journey_stage'] = label
    synchronize_test_plan(plan)
    before = deepcopy(plan)
    runner.validate_plan(plan)
    assert plan == before

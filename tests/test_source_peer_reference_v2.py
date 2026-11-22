"""Offline canonical-reference v2 prevention; no production recovery or paid calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sqlite3

import pytest

from scripts import run_source_first_selection as s
from src.orchestration import source_peer_evidence as peer
from tests.test_source_peer_evidence import request as legacy_request, MenuRegistry
from tests.test_source_first_selection_runner import research


# Captured from the unmodified v1 renderer before this feature was added.
V1_BYTES = {
    'position/narada': 'bec0cef7568847cffa040056201e30aa84956f042583e5785198062445f2f427',
    'position/shandilya': 'f0ccf5f6a70f57b3930090a8bd38b28e315b001d85c0f76e137437b55b5b314c',
    'position/researcher': '041e287f55b5ee1d4e224238e13b01a2286bb28165de35a41dba92aa10c3ae50',
    'position/sutrakar': '8fbeee46b556929b61ddd32bc9794d1231f4703e6b16c2104bdf14dfc64cac8a',
    'challenge/narada': '123e8d96b76fd3ecb0f594d2d173336b715f3202dbfedee8aabc87e4a28dfa77',
    'challenge/shandilya': '097569bcff655cea8f8d9dfd7569f9a35e524e6b3375da440d07691cc70c63ec',
    'challenge/researcher': '054783c3efab7235f05f109e8de0d6abf83d483802a30cae2907b150a2bef0d6',
    'challenge/sutrakar': 'e0c67ca9a11468aa1f6537a72a97202cec9ff5c59827d2621777893030910363',
    'reply/narada': '0ebb88dde5033b1e6abe7103ddc4bce97cad5491e10a51c6f5c321228ab2c5f2',
    'reply/shandilya': '4e708e5e5a4496709a8d3bb5f38eab3383a9bd47f8b0710575a530dda27c4b1f',
    'reply/researcher': '629fd46b1777a23297bacf242d6af7fa869771c240b9d29dac249ee5794a7f8f',
    'reply/sutrakar': '52186af3c65dc6358ace9c7090dee5d4c23b93584c75b3d4c050608dc95c5af7',
    'proposal/narada': '0e0ec57304ef9478fb91dcb38cf7dbe52d700322bb455113552833b1f09422f1',
    'proposal/shandilya': '726abfeccbb5fc55fe80b87d7eed74f078d9f0e2fcfaf956d027cd3b81ae5d60',
    'proposal/researcher': '6387c47564cc89f118891c2e5594092b5f792ff11b904c20f367af9690b0cb13',
    'proposal/sutrakar': 'f7183c9ac28841678ca19769e5a998370f936cb8fb7362fecfc8f884ac199a01',
    'peer_review/narada': '8e591759dae9905d7924cfcc23feaf1d15fefa9f88a566ccacaa224a6f7e77ab',
    'peer_review/shandilya': 'f38dbb1154706e3b613b338183a8cb9f7e866764f566f5592a24990b95447fd3',
    'peer_review/researcher': '11c09f1b4e9f0d924eabcf84378298f9b7ce080ac866192d0ce8d3380d08862a',
    'peer_review/sutrakar': 'ae48552885f06b92e5017cca2ed5fda015bb9d148ebaf655ad4cf15c37066f46',
}


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    """Fail before network, credentials or live adapters, including accidental probes."""
    def blocked(*args, **kwargs):
        pytest.fail('No network, credentials or live provider in reference-v2 tests')
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)
    monkeypatch.setattr(s, 'create_live_provider', blocked)
    monkeypatch.setattr('scripts.run_research_book.load_project_credentials', blocked)
    monkeypatch.setattr('src.providers.registry.ProviderRegistry', blocked)


def request(voice='sutrakar', stage='proposal'):
    """Use distinct synthetic entry-owned references and existing provenance aliases."""
    value = legacy_request((92, 93), voice, stage)
    value[peer.KEY] = peer.make_policy([], version=peer.REFERENCE_VERSION)
    for n, num in [(92, 2), (93, 3)]:
        ident = f'DEV-{num}'
        alias = f'N{num:03d}-S{num:03d}::{ident}'
        value['sources'][str(n)] = {
            'source_pair_ids': [f'N{num}', f'S{num}'], 'examples': [],
            'references': [{'id': i, 'original_text': f'मूळ पाठ {i}'} for i in [f'N{num}', f'S{num}', ident]],
            'source_contexts': {
                f'N{num}': {'id': num, 'meaning_mr': 'मूळ भक्तीचा अर्थ', 'context_mr': 'आध्यात्मिक संदर्भ'},
                ident: {'id': alias, 'source_id': ident, 'canonical_passage': f'मूळ पाठ {ident}',
                        'meaning_mr': 'अर्थ अक्षरशः जतन', 'context_mr': {'limits': ['सर्व मर्यादा जतन']}}},
            'research_interpretation': {'evidence_ids': [alias], 'relation_mr': 'अंशतः पूरक संबंध',
                'limitations_mr': 'देव म्हणजे नफा नाही', 'business_extension_mr': 'केवळ आधुनिक उपमा'}}
    return value


@pytest.mark.parametrize('key', list(V1_BYTES))
def test_v1_render_remains_byte_identical_to_prechange_capture(key):
    """Every role/stage keeps the exact original system/payload bytes and IDs."""
    stage, voice = key.split('/')
    assert peer.digest(peer.render(voice, legacy_request(voice=voice, stage=stage))) == V1_BYTES[key]


@pytest.mark.parametrize('stage', ['position', 'challenge', 'reply', 'proposal', 'peer_review'])
@pytest.mark.parametrize('voice', ['narada', 'shandilya', 'researcher', 'sutrakar'])
def test_v2_all_views_omit_only_competing_id_labels_and_preserve_source_text(stage, voice):
    """References/passages/context/limits and actual opinions never undergo repair."""
    payload = request(voice, stage); original = deepcopy(payload)
    baseline = s.writing_view(payload)['sources']
    expected = deepcopy(baseline)
    for packet in expected.values():
        packet['research_interpretation'].pop('evidence_ids')
        for context in packet['source_contexts'].values():
            if isinstance(context.get('id'), str) and '::' in context['id']:
                context.pop('id')
    rendered = peer.render(voice, payload); view = rendered['payload']['input']
    assert payload == original and view['sources'] == expected
    assert view['discussion'] == original['discussion'] and view['proposal'] == original['proposal']
    menu = view['canonical_reference_menu']
    assert menu['version'] == peer.REFERENCE_VERSION
    assert menu['entries']['92']['required_source_pair_ids'] == ['N2', 'S2']
    assert menu['entries']['92']['allowed_reference_ids'] == ['N2', 'S2', 'DEV-2']
    assert menu['entries']['93']['supplementary_reference_ids'] == ['DEV-3']
    assert all('::' not in i for row in menu['entries'].values() for i in row['allowed_reference_ids'])
    if stage == 'proposal':
        instruction = rendered['payload']['instruction']
        assert 'canonical_reference_menu' in instruction and 'without a comma' in instruction
        assert '2–4 words' in instruction and 'at most32' in instruction


@pytest.mark.parametrize('damage', ['foreign_entry', 'mismatched_sources', 'duplicate_id', 'missing_pair', 'no_supplement', 'namespaced_reference'])
def test_v2_menu_rejects_foreign_or_ambiguous_source_owners(damage):
    payload = request(); packet = payload['sources']['92']
    if damage == 'foreign_entry': payload['sources']['94'] = payload['sources'].pop('93')
    elif damage == 'mismatched_sources':
        payload['sources_by_entry'] = deepcopy(payload['sources']); payload['sources_by_entry']['92']['references'][0]['original_text'] += ' बदल'
    elif damage == 'duplicate_id': packet['references'].append(deepcopy(packet['references'][0]))
    elif damage == 'missing_pair': packet['source_pair_ids'] = ['N99', 'S2']
    elif damage == 'no_supplement': packet['references'].pop()
    else: packet['references'][-1]['id'] = 'N002-S002::DEV-2'
    with pytest.raises(ValueError): peer.render('sutrakar', payload)


def test_v2_menu_hash_binds_source_bytes_and_peer_selection_still_rejects_stale_input():
    """Same IDs with changed meaning alter bindings; stale peer materialization fails."""
    payload = request(stage='peer_review'); menu = peer.reference_menu(payload)
    old = peer.catalog(payload); binding = {k: old[k] for k in ('request_sha256', 'proposal_sha256', 'menu_sha256')}
    payload['sources']['92']['references'][0]['original_text'] += ' बदल'
    assert peer.reference_menu(payload)['menu_sha256'] != menu['menu_sha256']
    raw = {'reviews': [{'number': n, 'verdict': 'PASS', 'issues': []} for n in [92, 93]]}
    with pytest.raises(ValueError, match='Stale'): peer.materialize(raw, payload, binding)


def test_v2_only_provenance_labels_are_omitted_not_opinions_or_canonical_labels():
    """Even an alias quoted by a peer remains its unchanged native opinion."""
    payload = request(); packet = payload['sources']['92']
    packet['research_interpretation']['evidence_ids'].append('DEV-2')
    payload['discussion']['reply'] = {'narada': {'opinion': 'N002-S002::DEV-2 अशी मूळ नोंद'}}
    rendered = peer.render('sutrakar', payload)['payload']['input']
    assert rendered['sources']['92']['research_interpretation']['evidence_ids'] == ['DEV-2']
    assert rendered['discussion'] == payload['discussion']


def test_recovery_marker_is_server_only_even_in_new_peer_v1_views():
    """The newly introduced marker was absent from historical requests; votes stay exact."""
    payload = legacy_request(); payload['proposal']['exact_proposal_recovery'] = {'path': 'server-only'}
    rendered = peer.render('researcher', payload)['payload']['input']
    assert 'exact_proposal_recovery' not in rendered['proposal']
    assert rendered['proposal']['proposals'] == payload['proposal']['proposals']


def test_v2_freezes_per_batch_but_resumes_saved82_v1_with_v2_argument(tmp_path):
    """New policy choice applies only to subsequent wholly unstarted batches."""
    oldname = 'selection-' + '-'.join(map(str, range(82, 92)))
    v1 = peer.batch_policy(tmp_path, oldname, list(range(82, 92)), peer.VERSION, [], create=True)
    s.save(tmp_path / (oldname + '-input.json'), {'old': 'immutable'})
    saved = (tmp_path / (oldname + '-peer-policy.json')).read_bytes()
    assert peer.batch_policy(tmp_path, oldname, list(range(82, 92)), peer.REFERENCE_VERSION, []) == v1
    assert (tmp_path / (oldname + '-peer-policy.json')).read_bytes() == saved
    name = 'selection-92-93'
    assert peer.batch_policy(tmp_path, name, [92, 93], peer.REFERENCE_VERSION, [], create=False)['version'] == peer.REFERENCE_VERSION
    assert not (tmp_path / (name + '-peer-policy.json')).exists()
    v2 = peer.batch_policy(tmp_path, name, [92, 93], peer.REFERENCE_VERSION, [], create=True)
    assert peer.batch_policy(tmp_path, name, [92, 93], peer.VERSION, []) == v2


@pytest.mark.parametrize('state', ['old82', 'input', 'core', 'paid', 'unknown', 'unknown_saved', 'policy_drift'])
def test_v2_opt_in_rejects_old_started_unknown_or_drifted_batches(tmp_path, state):
    name = 'selection-92-93'; numbers = [92, 93]; requested = peer.REFERENCE_VERSION
    if state == 'old82': numbers = [82, 83]; name = 'selection-82-83'; s.save(tmp_path / (name + '-input.json'), {})
    elif state == 'input': s.save(tmp_path / (name + '-input.json'), {})
    elif state == 'core':
        dbp = tmp_path / ('council.db.batch-' + hashlib.sha256(peer._json(name).encode()).hexdigest() + '.sqlite3')
        with sqlite3.connect(dbp) as db:
            for table in ['research_runs', 'research_attempts', 'research_stages']: db.execute('CREATE TABLE ' + table + '(x)')
            db.execute('INSERT INTO research_attempts VALUES (1)')
    elif state == 'paid':
        (tmp_path / 'provider').mkdir()
        with sqlite3.connect(tmp_path / 'provider/boundary.db') as db:
            db.execute('CREATE TABLE calls(slot)'); db.execute('INSERT INTO calls VALUES (?)', (peer.digest(['sutrakar', f'batch/{name}/proposal']),))
    elif state in ('unknown', 'unknown_saved'):
        if state == 'unknown_saved': peer.batch_policy(tmp_path, name, numbers, requested, [], create=True)
        requested = 'invented-policy'
    else:
        peer.batch_policy(tmp_path, name, numbers, requested, [], create=True)
        path = tmp_path / (name + '-peer-policy.json'); saved = s.load(path); saved['policy']['version'] = peer.VERSION; s.save(path, saved)
    with pytest.raises(ValueError): peer.batch_policy(tmp_path, name, numbers, requested, [], create=True)


@pytest.fixture
def options(tmp_path, monkeypatch):
    """Isolate the real future92..101 runner batch with only fake model adapters."""
    plan, screening, refs = research(101); directory = tmp_path / 'inputs'; directory.mkdir()
    s.save(directory / 'research-stage-plan.json', plan); refpath = directory / 'refs.json'; s.save(refpath, refs)
    forbidden = directory / 'forbidden.json'; s.save(forbidden, ['चाचणीपुरती मूळ सूत्रनोंद'])
    monkeypatch.setattr(s, 'code_bindings', lambda: {'reference-fixture': 'a' * 64})
    gate = directory / 'gate.json'; s.save(gate, {'status': 'PASS', 'paid_calls': 0, 'code_sha256': s.code_bindings(),
        'tests': [{'path': p, 'passed': 1, 'failed': 0, 'errors': 0} for p in s.REQUIRED_TESTS]})
    monkeypatch.setattr(s, 'require_validator_calibration', lambda p: {'status': 'PASS', 'fixture': True})
    monkeypatch.setattr(s, 'load_selection_inputs', lambda p: {'stage_plan': deepcopy(plan), 'screening': deepcopy(screening),
        'input_provenance': {str(directory / 'research-stage-plan.json'): {'sha256': s.byte_hash(directory / 'research-stage-plan.json')}}})
    monkeypatch.setattr(s.book, 'planned_batches', lambda entries: [entries[91:101]])
    return dict(input_dir=directory, research_plan_sha256=s.byte_hash(directory / 'research-stage-plan.json'),
        pair_references_path=refpath, pair_references_sha256=s.byte_hash(refpath), forbidden_path=forbidden,
        offline_gate=gate, calibration_dir=directory / 'calibration', work=tmp_path / 'source',
        target=101, budget=100., claude_cap=80., max_calls=100,
        source_peer_policy=peer.REFERENCE_VERSION, committed_references=[])


def test_v2_real_runner_full_batch_native_peers_and_zero_call_resume(options):
    """All16 stages use the frozen v2 menus; native opinions and model caps stay intact."""
    registry = MenuRegistry(collision=False); out = s.run(**options, registry=registry)
    assert len(registry.calls) == 16 and len(out['accepted']) == 10
    work = Path(options['work']); candidate = s.load(work / 'candidate-092.json')
    bundle = s.load(work / candidate['discussion_file'])
    assert all(bundle['peer_review'][v]['reviews'][0]['verdict'] == 'PASS' for v in s.VOICES[:-1])
    for v in s.VOICES[:-1]:
        pointer = bundle['peer_review'][v][peer.MAPPING]
        assert s.load(pointer['path'])['kind'] == peer.REFERENCE_VERSION
    for call in registry.calls:
        envelope = json.loads(call['prompt']); view = envelope['input']
        assert view[peer.KEY]['version'] == peer.REFERENCE_VERSION
        assert set(view['canonical_reference_menu']['entries']) == set(map(str, range(92, 102)))
        assert call['tokens'] == 9000 and call['timeout'] == 240
        if call['voice'] == 'sutrakar': assert call['effort'] == 'low'
    before = len(registry.calls); s.run(**options, registry=registry, resume=True)
    assert len(registry.calls) == before


def test_v2_cache_menu_drift_fails_before_any_new_fake_call(options):
    """Mandatory v2 mapping replay checks exact saved request/menu bytes."""
    registry = MenuRegistry(collision=False); s.run(**options, registry=registry)
    work = Path(options['work']); candidate = s.load(work / 'candidate-092.json'); bundle = s.load(work / candidate['discussion_file'])
    proof = s.load(bundle['peer_review']['researcher'][peer.MAPPING]['path']); path = Path(proof['request_document']['path'])
    call = s.load(path); call['payload']['input']['canonical_reference_menu']['entries']['92']['allowed_reference_ids'].append('UNKNOWN'); s.save(path, call)
    before = len(registry.calls)
    with pytest.raises(s.SourceFirstStopped): s.run(**options, registry=registry, resume=True)
    assert len(registry.calls) == before


@pytest.mark.parametrize('damage', ['alias', 'comma'])
def test_v2_never_repairs_native_invalid_ids_or_formula(options, damage):
    """Prompt prevention does not silently canonicalize native outputs or waive old gates."""
    class BadNative(MenuRegistry):
        def respond(self, voice, payload):
            value = super().respond(voice, payload)
            if payload['stage'] == 'proposal':
                if damage == 'alias': value['proposals'][0]['selected_source_ids'][-1] = 'N002-S002::UNKNOWN'
                else: value['proposals'][0]['proposed_sutra'] = 'उद्यमेन, विवेकः'
            return value
    registry = BadNative(collision=False)
    with pytest.raises(s.SourceFirstStopped): s.run(**options, registry=registry)
    assert len(registry.calls) == 14
    assert not (Path(options['work']) / 'candidate-092.json').exists()
    raws = [p.read_text(encoding='utf-8') for p in (Path(options['work']) / 'provider/raw').glob('*.txt')]
    needle = 'N002-S002::UNKNOWN' if damage == 'alias' else 'उद्यमेन, विवेकः'
    assert sum(needle in raw for raw in raws) == 2


def test_saved_v1_batch_replays_unchanged_before_new_v2_batch(options, monkeypatch):
    """An actual fake-paid82 batch stays v1 when92 is opted into v2 on resume."""
    monkeypatch.setattr(s.book, 'planned_batches', lambda entries: [entries[81:91], entries[91:101]])
    old = {**options, 'source_peer_policy': peer.VERSION, 'target': 91}
    registry = MenuRegistry(collision=False); s.run(**old, registry=registry)
    work = Path(options['work']); assert len(registry.calls) == 16
    protected = [*work.glob('selection-*-input.json'), *work.glob('selection-*-discussion.json'),
        *work.glob('*-peer-policy.json'), *work.glob('candidate-*.json'),
        *(work / 'peer-evidence').glob('*.json'), *(work / 'provider/raw').glob('*.txt')]
    before = {p: p.read_bytes() for p in protected}
    s.run(**options, registry=registry, resume=True)
    assert len(registry.calls) == 32 and all(p.read_bytes() == raw for p, raw in before.items())
    assert all(json.loads(c['prompt'])['input'][peer.KEY]['version'] == peer.VERSION for c in registry.calls[:16])
    assert all(json.loads(c['prompt'])['input'][peer.KEY]['version'] == peer.REFERENCE_VERSION for c in registry.calls[16:])
    s.run(**options, registry=registry, resume=True); assert len(registry.calls) == 32


def test_only_own_reference_subset_is_accepted_by_unchanged_metadata_gate():
    """The menu does not waive both-sutra or existing own-supplement requirements."""
    payload = request(); packet = payload['sources']['92']
    row = {'number': 92, 'decision': 'ACCEPT', 'proposed_sutra': 'उद्यमेन विवेकः',
        'topic_mr': 'चाचणी विषय', 'business_decision_mr': 'चाचणी निर्णय कोणत्या परिस्थितीत निवडायचा ठरवणे',
        'business_action_mr': 'चाचणी कृती ठराविक परिस्थितीत प्रत्यक्ष करून पाहणे',
        'journey_stage': 'practice', 'selected_source_ids': ['N2', 'S2', 'DEV-2']}
    s.validate_metadata({'proposals': [row]}, {'92': packet})
    for invalid in [['N2', 'S2'], ['N2', 'S2', 'DEV-3'], ['N2', 'S2', 'N002-S002::DEV-2'], ['N2', 'DEV-2']]:
        damaged = {**row, 'selected_source_ids': invalid}
        with pytest.raises(ValueError): s.validate_metadata({'proposals': [damaged]}, {'92': packet})


def test_unknown_runner_policy_fails_before_output_or_fake_provider(options):
    """Unknown flags cannot silently become v1/v2 or reach source/model setup."""
    registry = MenuRegistry(collision=False)
    with pytest.raises(ValueError, match='Explicit future policy'):
        s.run(**{**options, 'source_peer_policy': 'unknown-policy'}, registry=registry)
    assert not Path(options['work']).exists() and not registry.calls


def test_cli_accepts_only_explicit_registered_v2_choice(tmp_path, monkeypatch):
    """CLI opt-in passes the exact new version; the default remains absent."""
    refs = tmp_path / 'committed.json'; s.save(refs, [])
    captured = {}
    def capture(**kwargs):
        captured.update(kwargs); return {'status': 'TEST_ONLY_NO_EXECUTION'}
    monkeypatch.setattr(s, 'run', capture)
    args = sum(([f'--{name}', 'fixture'] for name in ['input-dir', 'research-plan-sha256', 'pair-references',
        'pair-references-sha256', 'forbidden', 'offline-gate', 'calibration-dir', 'work']), [])
    assert s.main(args + ['--future-peer-policy', peer.REFERENCE_VERSION, '--committed-references', str(refs)]) == 0
    assert captured['source_peer_policy'] == peer.REFERENCE_VERSION and captured['committed_references'] == []


@pytest.mark.parametrize('voice', ['narada', 'shandilya', 'researcher'])
def test_v2_peer_shape_counts_are_current_and_never_grammar_approval(voice):
    """All three peers get exact existing shape counts and whole-field review guidance."""
    payload = request(voice, 'peer_review')
    proposal = payload['proposal']['proposals'][0]
    proposal.update(decision='ACCEPT', proposed_sutra='शीलं प्रथमं कौशलं पश्चात्',
        derivation='हे आजचे अर्थान्वयन आहे; मूळ स्रोताचा थेट व्यावसायिक उपदेश नाही.')
    original = deepcopy(payload)
    rendered = peer.render(voice, payload); shape = rendered['payload']['input']['current_formula_shapes']
    assert set(shape) == {'92'} and shape['92'] == {
        'formula_exact': proposal['proposed_sutra'], 'counted_text': proposal['proposed_sutra'],
        'word_count': 4, 'unicode_character_count': len(proposal['proposed_sutra']), 'grammar_approval': False}
    assert payload == original and rendered['payload']['input']['proposal'] == original['proposal']
    instruction = rendered['payload']['instruction']
    for clause in ['NOT grammar approval', 'WHOLE current field', 'remaining false or unsupported claim',
                   'ancient hiring/business vocabulary alone', 'concrete erroneous form',
                   'with its derivation', 'unsupported mandatory-sutra claims', 'no acceptance waiver']:
        assert clause in instruction


def test_v2_shape_display_mirrors_existing_count_scope_without_repair():
    """Trimmed terminal dandas/spaces match the old gate; a comma remains an error."""
    payload = request('researcher', 'peer_review'); proposal = payload['proposal']['proposals'][0]
    proposal.update(decision='ACCEPT', proposed_sutra='  ॥शीलं प्रथमं, कौशलं पश्चात्॥  ')
    old = deepcopy(payload)
    shape = peer.render('researcher', payload)['payload']['input']['current_formula_shapes']['92']
    assert shape['formula_exact'] == proposal['proposed_sutra'] and shape['counted_text'] == 'शीलं प्रथमं, कौशलं पश्चात्'
    assert shape['word_count'] == 4 and shape['unicode_character_count'] == len(shape['counted_text'])
    assert shape['grammar_approval'] is False and payload == old
    from src.orchestration.research_council import _short_sutra
    with pytest.raises(ValueError, match='compound'): _short_sutra(proposal['proposed_sutra'])


def test_v2_prompt_clarity_never_drops_or_normalizes_native_peer_opinions():
    """Even an objection discouraged by the prompt remains the actual native vote."""
    payload = request('researcher', 'peer_review')
    payload['proposal']['proposals'][0].update(decision='ACCEPT', proposed_sutra='शीलं प्रथमं कौशलं पश्चात्')
    menu = peer.catalog(payload); bound = {k: menu[k] for k in ('request_sha256', 'proposal_sha256', 'menu_sha256')}
    raw = {'reviews': [{'number': 92, 'verdict': 'REVIEW_REQUIRED', 'issues': [
        {'evidence_id': 'P092.proposed_sutra', 'reason': 'Please confirm whether this grammar is awkward.', 'severity': 'medium'}]},
        {'number': 93, 'verdict': 'PASS', 'issues': []}]}
    old = deepcopy(raw); canonical, _ = peer.materialize(raw, payload, bound)
    assert raw == old and canonical['reviews'][0]['verdict'] == 'REVIEW_REQUIRED'
    assert canonical['reviews'][0]['issues'][0]['reason'] == raw['reviews'][0]['issues'][0]['reason']
    assert canonical['reviews'][0]['issues'][0]['quote'] == payload['proposal']['proposals'][0]['proposed_sutra']


def test_v2_shape_metadata_is_only_for_current_peer_review():
    """No v1 request or pre-proposal view acquires the new review-only metadata."""
    for stage in ['position', 'challenge', 'reply', 'proposal']:
        assert 'current_formula_shapes' not in peer.render('sutrakar', request('sutrakar', stage))['payload']['input']
    assert 'current_formula_shapes' not in peer.render('researcher', legacy_request())['payload']['input']

"""Offline fake-only tests. No credentials, paid APIs, new business Sanskrit or exports."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import run_source_first_selection as runner
from tests.test_source_first_book_plan import fixture, bundle, seal
from tests.test_source_first_book_runner import Registry


class SelectionRegistry(Registry):
    """Existing fixed five fake adapters; metadata are explicitly synthetic fixtures."""
    def respond(self, voice, payload):
        """Offline helper: respond. Uses explicit fixtures; returns test data or raises on unexpected wiring."""
        assert voice != 'validator'
        assert payload['stage'] in ('position', 'challenge', 'reply', 'proposal', 'peer_review')
        assert payload['role_focus'] == runner.ROLE_FOCUS[voice]
        assert 'prior_accepted_decisions' in payload
        for source in payload['sources'].values():
            assert source['examples'] == []
            assert 'case_inventory' not in source
            assert 'selection_provenance' not in source
            assert len(source['source_pair_ids']) == 2
        result = super().respond(voice, payload)
        if payload['stage'] == 'proposal':
            for proposal in result['proposals']:
                if proposal['decision'] == 'ACCEPT':
                    n = proposal['number']
                    proposal.update(topic_mr=f'चाचणी विषय {n}',
                                    business_decision_mr=f'चाचणी निर्णय कोणत्या परिस्थितीत निवडायचा ठरवणे {n}',
                                    business_action_mr=f'चाचणी कृती ठराविक परिस्थितीत प्रत्यक्ष करून पाहणे {n}', journey_stage='practice')
        if payload['stage'] == 'peer_review':
            for p in payload['proposal']['proposals']:
                if p['decision'] == 'ACCEPT':
                    assert p['business_decision_mr'].startswith('चाचणी')
                    assert p['business_action_mr'].startswith('चाचणी')
        return result


def research(count=3):
    """Offline helper: research. Uses explicit fixtures; returns test data or raises on unexpected wiring."""
    args = fixture()
    plan = args['stage_plan']
    seed = deepcopy(plan['candidates'][0])
    refs = deepcopy(args['pair_references'])
    plan['candidates'] = []
    for index in range(count):
        n, sh = 2 + index % 83, 2 + index // 83
        c = deepcopy(seed)
        c['id'] = f'N{n:03d}-S{sh:03d}'
        c['shandilya']['id'] = sh
        sref = deepcopy(refs['S2']);sref.update(id=f'S{sh}', locator=f'S{sh}')
        refs[f'S{sh}'] = sref
        c['narada']['id'] = n
        plan['candidates'].append(c)
        ref = deepcopy(refs['N2']);ref.update(id=f'N{n}', locator=f'N{n}')
        refs[f'N{n}'] = ref
    ids = [c['id'] for c in plan['candidates']]
    plan['candidate_count'] = len(ids)
    plan['batches'] = [ids[i:i+20] for i in range(0, len(ids), 20)]
    seal(plan)
    return plan, {f'research-{i:03d}': bundle(plan, i) for i in range(1, len(plan['batches'])+1)}, refs


@pytest.fixture(autouse=True)
def no_live(monkeypatch):
    """Offline helper: no live. Uses explicit fixtures; returns test data or raises on unexpected wiring."""
    def blocked(*args, **kwargs):
        """Offline helper: blocked. Uses explicit fixtures; returns test data or raises on unexpected wiring."""
        pytest.fail('Live providers/credentials are forbidden in these tests')
    monkeypatch.setattr(runner, 'create_live_provider', blocked)
    monkeypatch.setattr('scripts.run_research_book.load_project_credentials', blocked)
    monkeypatch.setattr('src.providers.registry.ProviderRegistry', blocked)


@pytest.fixture
def options(tmp_path, monkeypatch):
    """Offline helper: options. Uses explicit fixtures; returns test data or raises on unexpected wiring."""
    plan, screening, refs = research(12)
    directory = tmp_path/'inputs';directory.mkdir()
    runner.save(directory/'research-stage-plan.json', plan)
    refs_path = directory/'refs.json';runner.save(refs_path, refs)
    forbidden = directory/'forbidden.json';runner.save(forbidden, ['चाचणीपुरती मूळ सूत्रनोंद'])
    # Only the gate implementation and real calibration are stubbed for wiring;
    # their failure cases and the real code seal are exercised separately.
    monkeypatch.setattr(runner, 'code_bindings', lambda: {'selection-fixture': 'a'*64})
    gate = directory/'gate.json'
    runner.save(gate, {'status':'PASS','paid_calls':0,'code_sha256':runner.code_bindings(),
        'tests':[{'path':p,'passed':1,'failed':0,'errors':0} for p in runner.REQUIRED_TESTS]})
    monkeypatch.setattr(runner, 'require_validator_calibration', lambda path: {'status':'PASS','fixture':True})
    monkeypatch.setattr(runner, 'load_selection_inputs', lambda path: {
        'stage_plan':deepcopy(plan),'screening':deepcopy(screening),'input_provenance':{
            str(directory/'research-stage-plan.json'):{'sha256':runner.byte_hash(directory/'research-stage-plan.json')}}})
    return dict(input_dir=directory,research_plan_sha256=runner.byte_hash(directory/'research-stage-plan.json'),
        pair_references_path=refs_path,pair_references_sha256=runner.byte_hash(refs_path),
        forbidden_path=forbidden,offline_gate=gate,calibration_dir=directory/'calibration',
        work=tmp_path/'selection',budget=50.,claude_cap=40.,max_calls=300)


def envelopes(registry):
    """Offline helper: envelopes. Uses explicit fixtures; returns test data or raises on unexpected wiring."""
    return [json.loads(c['prompt']) for c in registry.calls]


def test_exhaustive_124_includes_every_pair_without_curator_case_inputs():
    """Offline assertion: exhaustive 124 includes every pair without curator case inputs. Fixtures in; no return; failure identifies the violated invariant."""
    plan, screening, refs = research(124)
    selection = runner.build_selection(plan,screening,refs)
    assert len(selection['entries']) == 124
    assert [e['candidate_id'] for e in selection['entries']] == [c['id'] for c in plan['candidates']]
    assert [len(b) for b in runner.book.planned_batches(selection['entries'])] == [1]+[10]*12+[3]
    for e in selection['entries']:
        assert e['source_packet']['examples'] == []
        assert 'business_action_mr' not in e['brief']
        assert 'journey_stage' not in e['brief']
        r = e['source_packet']['research_interpretation']
        assert e['brief']['qualified_business_hypothesis_mr'] == r['business_extension_mr']
        assert e['brief']['source_core_mr'] == r['source_core_mr']
        assert e['source_packet']['selection_provenance']['independent_review']['verdict'] == 'PASS'


def test_pending_exclusion_not_completeness_block():
    """Offline assertion: pending exclusion not completeness block. Fixtures in; no return; failure identifies the violated invariant."""
    plan, screening, refs = research()
    pending = plan['candidates'][0]['id']
    screening['research-001'] = bundle(plan,1,statuses={pending:'PENDING'})
    selection = runner.build_selection(plan,screening,refs)
    assert len(selection['entries']) == 2
    assert pending not in [e['candidate_id'] for e in selection['entries']]


def test_missing_batch_blocks():
    """Offline assertion: missing batch blocks. Fixtures in; no return; failure identifies the violated invariant."""
    plan,screening,refs=research(21)
    del screening['research-002']
    with pytest.raises(ValueError,match='Complete research'):
        runner.build_selection(plan,screening,refs)


def test_source_or_gate_drift_blocks():
    """Offline assertion: source or gate drift blocks. Fixtures in; no return; failure identifies the violated invariant."""
    plan,screening,refs=research()
    screening['research-001']['gate']['selection_sha256']='0'*64
    with pytest.raises(ValueError):runner.build_selection(plan,screening,refs)


def test_wrong_canonical_meaning_blocks():
    """Offline assertion: wrong canonical meaning blocks. Fixtures in; no return; failure identifies the violated invariant."""
    plan,screening,refs=research()
    refs['N2']['meaning_mr']='बदललेला अर्थ'
    with pytest.raises(ValueError,match='drift'):runner.build_selection(plan,screening,refs)


def test_default_preflight_does_not_make_output_or_adapters(options):
    """Offline assertion: default preflight does not make output or adapters. Fixtures in; no return; failure identifies the violated invariant."""
    result=runner.run(**options)
    assert result['status']=='OFFLINE_PREFLIGHT_PASS'
    assert not options['work'].exists()


def test_pilot_then_full_resume_exact_cache_and_history(options):
    """Offline assertion: pilot then full resume exact cache and history. Fixtures in; no return; failure identifies the violated invariant."""
    fake=SelectionRegistry(rejected=(3,))
    first=runner.run(**options,target=1,registry=fake)
    assert first['status']=='SELECTION_CHECKPOINT'
    assert len(fake.calls)==16
    assert fake.maximum_active==1
    pilot=(options['work']/'selection-1-discussion.json').read_bytes()
    second=runner.run(**options,resume=True,registry=fake)
    assert second['status']=='SELECTION_COMPLETE'
    assert len(second['considered'])==12
    assert len(fake.calls)==48
    assert second['rejected']==['N004-S002']
    assert second['composition_calls']==second['validator_calls']==0
    assert pilot==(options['work']/'selection-1-discussion.json').read_bytes()
    all_views=[e['input'] for e in envelopes(fake)]
    batches={str(e['entry_numbers']):e for e in all_views}
    assert batches['[1]']['prior_accepted_decisions']==[]
    history=batches[str(list(range(2,12)))]['prior_accepted_decisions']
    assert [h['number'] for h in history]==[1]
    assert [h['number'] for h in batches['[12]']['prior_accepted_decisions']]==[1,2,4,5,6,7,8,9,10,11]
    for e in envelopes(fake):
        view=e['input']
        if view['stage']=='peer_review':
            assert 'business_decision_mr' in e['instruction']
            assert 'journey_stage' in e['instruction']
        assert all('selection_history' not in b for b in view['briefs'])
        assert all('selection_provenance' not in s for s in view['sources'].values())
    before=len(fake.calls)
    runner.run(**options,resume=True,registry=fake)
    assert len(fake.calls)==before
    ledger=runner.load(options['work']/'selection-ledger.json')
    assert len(ledger['candidates'])==12
    assert len(ledger['prior_accepted_decisions'])==11


def test_target_finishes_containing_stable_batch(options):
    """Offline assertion: target finishes containing stable batch. Fixtures in; no return; failure identifies the violated invariant."""
    fake=SelectionRegistry()
    result=runner.run(**options,target=2,registry=fake)
    assert len(result['considered'])==11
    assert len(fake.calls)==32
    assert result['status']=='SELECTION_CHECKPOINT'


@pytest.mark.parametrize('field,value', [('topic_mr','English only'),('business_decision_mr',''),
    ('business_action_mr',None),('journey_stage','MBA'),('selected_source_ids',['N2','S2'])])
def test_invalid_accept_metadata_and_supplementary_fail(field,value):
    """Offline assertion: invalid accept metadata and supplementary fail. Fixtures in; no return; failure identifies the violated invariant."""
    plan,screening,refs=research()
    entry=runner.build_selection(plan,screening,refs)['entries'][0]
    packet=entry['source_packet']
    p={'number':1,'decision':'ACCEPT','topic_mr':'चाचणी','business_decision_mr':'चाचणी निर्णय कोणत्या परिस्थितीत निवडायचा ठरवणे',
       'business_action_mr':'चाचणी कृती ठराविक परिस्थितीत प्रत्यक्ष करून पाहणे','journey_stage':'opening',
       'selected_source_ids':[r['id'] for r in packet['references']]}
    p[field]=value
    with pytest.raises(ValueError):runner.validate_metadata({'proposals':[p]},{'1':packet})


def test_sutrakar_metadata_is_peer_reviewed_not_offline(options):
    """Offline assertion: sutrakar metadata is peer reviewed not offline. Fixtures in; no return; failure identifies the violated invariant."""
    fake=SelectionRegistry()
    result=runner.run(**options,target=1,registry=fake)
    row=runner.load(options['work']/'candidate-001.json')
    assert set(row['peer_review'])==set(runner.VOICES)-{'sutrakar'}
    assert row['proposal']['business_action_mr']=='चाचणी कृती ठराविक परिस्थितीत प्रत्यक्ष करून पाहणे 1'
    assert result['accepted']==['N002-S002']


def test_each_role_has_explicit_focus_and_settings(options):
    """Offline assertion: each role has explicit focus and settings. Fixtures in; no return; failure identifies the violated invariant."""
    fake=SelectionRegistry()
    runner.run(**options,target=1,registry=fake)
    for call in fake.calls:
        env=json.loads(call['prompt']);voice=call['voice']
        assert runner.ROLE_FOCUS[voice] in call['system']
        assert env['input']['role_focus']==runner.ROLE_FOCUS[voice]
        assert 'immortality with corporate longevity' in call['system']
        assert 'shared broad source concepts alone do NOT' in call['system']
        assert call['timeout']==240
        assert call['tokens']==4096
        if runner.PROVIDERS[voice]=='anthropic':assert call['effort']=='low'
    assert set(c['voice'] for c in fake.calls)==set(runner.VOICES)
    assert runner.MODELS==runner.book.MODELS


@pytest.mark.parametrize('stage',['composition','composition_v2_1','independent_review'])
def test_no_composition_contract(stage):
    """Offline assertion: no composition contract. Fixtures in; no return; failure identifies the violated invariant."""
    with pytest.raises(ValueError,match='prohibits'):runner.selection_contract(stage,{})


@pytest.mark.parametrize('change',['caps','reference','forbidden'])
def test_resume_rejects_drift_before_calls(options,change):
    """Offline assertion: resume rejects drift before calls. Fixtures in; no return; failure identifies the violated invariant."""
    fake=SelectionRegistry();runner.run(**options,target=1,registry=fake)
    altered=dict(options)
    if change=='caps':altered['budget']+=1
    elif change=='reference':runner.save(options['pair_references_path'],{})
    else:runner.save(options['forbidden_path'],['बदललेली नोंद'])
    with pytest.raises(ValueError):runner.run(**altered,resume=True,registry=fake)
    assert len(fake.calls)==16


@pytest.mark.parametrize('fault',['stale','missing','zero','failed','duplicate'])
def test_offline_receipt_fail_closed_before_live(options,fault):
    """Offline assertion: offline receipt fail closed before live. Fixtures in; no return; failure identifies the violated invariant."""
    gate=runner.load(options['offline_gate'])
    if fault=='stale':gate['code_sha256']={}
    elif fault=='missing':gate['tests'].pop()
    elif fault=='zero':gate['tests'][0]['passed']=0
    elif fault=='failed':gate['tests'][0]['failed']=1
    else:gate['tests'].append(deepcopy(gate['tests'][0]))
    runner.save(options['offline_gate'],gate)
    with pytest.raises(ValueError):runner.run(**options,live=True,credentials_dir='never-load')


def test_failed_calibration_before_live(options,monkeypatch):
    """Offline assertion: failed calibration before live. Fixtures in; no return; failure identifies the violated invariant."""
    def fail(path):
        """Offline helper: fail. Uses explicit fixtures; returns test data or raises on unexpected wiring."""
        raise ValueError('Calibration failed')
    monkeypatch.setattr(runner,'require_validator_calibration',fail)
    with pytest.raises(ValueError,match='Calibration'):runner.run(**options,live=True,credentials_dir='never-load')


def test_real_code_seal_includes_own_and_reused_code():
    """Offline assertion: real code seal includes own and reused code. Fixtures in; no return; failure identifies the violated invariant."""
    proof=runner.code_bindings()
    for name in ('scripts/run_source_first_selection.py','tests/test_source_first_selection_runner.py',
                 'src/orchestration/research_council.py','src/orchestration/source_first_provider.py',
                 'src/orchestration/source_first_writing.py','scripts/run_source_first_book.py'):
        assert proof[name]==runner.byte_hash(runner.ROOT/name)
    assert set(runner.REQUIRED_TESTS).issubset(proof)


def test_source_only_loader_no_case_dependency(tmp_path):
    """Offline assertion: source only loader no case dependency. Fixtures in; no return; failure identifies the violated invariant."""
    plan,screening,_=research()
    # Fixture hashes are synthetic; no external sources declared for this I/O-only check.
    plan['source_hashes']={};seal(plan)
    runner.save(tmp_path/'research-stage-plan.json',plan)
    for name,data in screening.items():
        for kind in ('request','selection','gate'):
            runner.save(tmp_path/'research-screening'/f'{name}-{kind}.json',data[kind])
    result=runner.load_selection_inputs(tmp_path)
    assert len(result['screening'])==1
    assert not any('case' in path for path in result['input_provenance'])


def test_output_cannot_overlap_inputs(options):
    """Offline assertion: output cannot overlap inputs. Fixtures in; no return; failure identifies the violated invariant."""
    options['work']=options['input_dir']
    with pytest.raises(ValueError,match='disjoint'):runner.run(**options)


def test_peer_objection_holds_accept_without_retry_or_lost_history(options):
    """Offline assertion: peer objection holds accept without retry or lost history. Fixtures in; no return; failure identifies the violated invariant."""
    class ObjectingRegistry(SelectionRegistry):
        def respond(self,voice,payload):
            """Offline helper: respond. Uses explicit fixtures; returns test data or raises on unexpected wiring."""
            result=super().respond(voice,payload)
            if payload['stage']=='peer_review' and voice=='narada':
                for review in result['reviews']:
                    if review['number']==1:
                        review.update(verdict='REVIEW_REQUIRED',issues=[{
                            'field':'business_action_mr','quote':'चाचणी कृती',
                            'reason':'Synthetic substantive objection for hold wiring only',
                            'severity':'major'}])
            return result
    fake=ObjectingRegistry()
    result=runner.run(**options,target=2,registry=fake)
    assert result['held_peer_review']==['N002-S002']
    assert 'N002-S002' not in result['accepted']
    assert len(fake.calls)==32
    row=runner.load(options['work']/'candidate-001.json')
    assert row['status']=='HOLD_PEER_REVIEW'
    assert row['case_curation_eligible'] is False
    assert row['composition_approved'] is False
    assert row['peer_review']['narada']['issues'][0]['field']=='business_action_mr'
    view=next(e['input'] for e in envelopes(fake) if e['input']['entry_numbers']==list(range(2,12)))
    assert view['prior_accepted_decisions']==[]
    assert view['held_selection_decisions'][0]['status']=='HOLD_PEER_REVIEW'
    assert view['held_selection_decisions'][0]['peer_disputed'] is True
    assert 'N003-S002' in result['accepted']
    assert len(runner.load(options['work']/'selection-ledger.json')['prior_accepted_decisions'])==11


def test_resume_lower_target_cannot_overwrite_completed_ledger(options):
    """Offline assertion: resume lower target cannot overwrite completed ledger. Fixtures in; no return; failure identifies the violated invariant."""
    fake=SelectionRegistry()
    runner.run(**options,target=2,registry=fake)
    before=(options['work']/'selection-ledger.json').read_bytes()
    with pytest.raises(ValueError,match='regress'):
        runner.run(**options,resume=True,target=1,registry=fake)
    assert before==(options['work']/'selection-ledger.json').read_bytes()
    assert len(fake.calls)==32


def test_missing_metadata_stops_before_peer_reviews(options):
    """Offline assertion: missing metadata stops before peer reviews. Fixtures in; no return; failure identifies the violated invariant."""
    class MissingMetadata(SelectionRegistry):
        def respond(self,voice,payload):
            """Offline helper: respond. Uses explicit fixtures; returns test data or raises on unexpected wiring."""
            result=super().respond(voice,payload)
            if payload['stage']=='proposal':
                result['proposals'][0].pop('business_action_mr')
            return result
    fake=MissingMetadata()
    with pytest.raises(runner.SourceFirstStopped):runner.run(**options,target=1,registry=fake)
    assert not any(e['input']['stage']=='peer_review' for e in envelopes(fake))
    assert not (options['work']/'candidate-001.json').exists()
    assert sum(e['input']['stage']=='proposal' for e in envelopes(fake))==2


def test_updated_current_test_receipt_preserves_paid_cache_binding(options):
    """Offline assertion: updated current test receipt preserves paid cache binding. Fixtures in; no return; failure identifies the violated invariant."""
    fake=SelectionRegistry()
    runner.run(**options,target=1,registry=fake)
    manifest=(options['work']/'run-manifest.json').read_bytes()
    gate=runner.load(options['offline_gate'])
    gate['tests'][0]['passed']=2
    # A parser/test-only code fix has a new required code seal, not new sources.
    from unittest.mock import patch
    gate['code_sha256']={'selection-fixture':'b'*64}
    gate['execution_note']='New tested invocation, same immutable business inputs'
    runner.save(options['offline_gate'],gate)
    with patch.object(runner,'code_bindings',return_value=gate['code_sha256']):
        runner.run(**options,resume=True,target=1,registry=fake)
    assert len(fake.calls)==16
    assert manifest==(options['work']/'run-manifest.json').read_bytes()
    receipts=sorted((options['work']/'execution-receipts').glob('*.json'))
    assert len(receipts)==2
    first,second=[runner.load(p) for p in receipts]
    assert first['offline_gate_sha256']!=second['offline_gate_sha256']
    assert first['binding']==second['binding']
    assert 'offline_gate' not in first['binding']


def test_changed_prompt_contract_cannot_silently_reuse_council_cache(options,monkeypatch):
    """Offline assertion: changed prompt contract cannot silently reuse council cache. Fixtures in; no return; failure identifies the violated invariant."""
    fake=SelectionRegistry()
    runner.run(**options,target=1,registry=fake)
    monkeypatch.setattr(runner,'SELECTION_SYSTEM',runner.SELECTION_SYSTEM+' Changed semantic instruction.')
    with pytest.raises(ValueError,match='Resume bindings'):
        runner.run(**options,resume=True,target=1,registry=fake)
    assert len(fake.calls)==16


class FramingRegistry(SelectionRegistry):
    """Attach a controlled suffix to one fake paid response; no SDK exists here."""
    def __init__(self,suffix):
        """Input: exact test suffix. Return a fixed fake registry; no credentials."""
        super().__init__()
        self.suffix=suffix

    def generate(self,voice,adapter,prompt,system):
        """Return the original synthetic response plus suffix only for proposal.

        Inputs are existing fake dispatch arguments. No retry or parsing occurs
        here; provider/council errors remain observable to the calling test.
        """
        response=super().generate(voice,adapter,prompt,system)
        if json.loads(prompt)['input']['stage']=='proposal':response.content+=self.suffix
        return response


def test_single_extra_brace_reuses_one_sdk_response_and_preserves_proof(options):
    """Assert exact surplus-brace recovery, raw/proof retention and free resume."""
    import sqlite3
    fake=FramingRegistry('}')
    result=runner.run(**options,target=1,registry=fake)
    assert result['accepted']==['N002-S002']
    assert len(fake.calls)==16
    assert sum(e['input']['stage']=='proposal' for e in envelopes(fake))==1
    provider_dir=options['work']/'provider'
    with sqlite3.connect(provider_dir/'boundary.db') as db:
        proofs=[json.loads(row[0]) for row in db.execute('SELECT record_json FROM json_framing_recoveries')]
    assert len(proofs)==1
    proof=proofs[0]
    assert proof['new_provider_calls']==0
    assert proof['semantic_content_changed'] is False
    assert proof['raw_bytes_changed'] is False
    raws=list((provider_dir/'raw').glob('*.txt'))
    original=[p for p in raws if runner.byte_hash(p)==proof['original_raw_sha256']]
    assert len(original)==1 and original[0].read_text(encoding='utf-8').endswith('}}')
    runner.run(**options,resume=True,target=1,registry=fake)
    assert len(fake.calls)==16


@pytest.mark.parametrize('suffix',['} arbitrary correction','\nCorrection: use another source','}}'])
def test_ambiguous_trailing_text_stops_without_second_sdk(options,suffix):
    """Assert non-lossless suffixes stop on the first proposal response, no peers."""
    fake=FramingRegistry(suffix)
    with pytest.raises(runner.SourceFirstStopped):runner.run(**options,target=1,registry=fake)
    assert sum(e['input']['stage']=='proposal' for e in envelopes(fake))==1
    assert len(fake.calls)==13
    assert not any(e['input']['stage']=='peer_review' for e in envelopes(fake))
    assert not (options['work']/'candidate-001.json').exists()



def test_new_output_subdirectory_can_be_disjoint_from_frozen_files(options):
    """A fresh task-side subdirectory is safe when no source/gate tree overlaps."""
    options['work']=options['input_dir']/'new-selection-output'
    result=runner.run(**options)
    assert result['status']=='OFFLINE_PREFLIGHT_PASS'
    assert not options['work'].exists()



def optional_supplement_fixture(count=3, *, evidence=None):
    """Return plan/screening/refs and a synthetic approved optional proof bundle.

    Ancient quote is the existing structural Gita fixture, not invented saint
    material or a public-source verification claim. Useful to packet consumers.
    """
    from tests.test_source_first_book_plan import PROSE, QUOTE
    plan,screening,refs=research(count)
    evidence=evidence or runner.preparation.research_coverage(plan,screening)['eligible'][plan['candidates'][0]['id']]
    record={'id':'MRB-STRUCTURAL-TEST','status':'VERIFIED','blockers':[],
        'work':'Structural fixture, not a saint attribution','author':'Synthetic structural fixture',
        'exact_short_passage':QUOTE,'passage_sha256':runner.preparation.byte_hash(QUOTE.encode()),
        'faithful_meaning_mr':PROSE,'original_devotional_context_mr':PROSE,
        'primary_url':'https://example.org/structural-fixture','verification_level':'SYNTHETIC_TEST_ONLY',
        'edition':{'name':'Fixture edition'},'locator':{'printed_page':1},
        'checked_date_local':'2026-11-21','timezone':'Asia/Calcutta','transcription_note_mr':PROSE,
        'limits_mr':[PROSE],'verification_proof':{'synthetic':True},'rights':{'fixture':True},
        'meaning_review_status':'PROVISIONAL','publication_approval':'NOT_ASSESSED'}
    catalog={'records':[record]}
    context={k:deepcopy(record[k]) for k in ('verification_level','edition','locator','checked_date_local',
        'timezone','transcription_note_mr','original_devotional_context_mr','limits_mr','verification_proof',
        'rights','meaning_review_status','publication_approval','blockers')}
    context.update(catalog_record_id=record['id'],catalog_record_status=record['status'],
        pair_source_contexts={name:{k:deepcopy(evidence['candidate'][name][k]) for k in
            ('id','meaning_mr','context_mr','source_note') if k in evidence['candidate'][name]}
            for name in ('narada','shandilya')})
    row={'id':record['id'],'pair_id':evidence['candidate']['id'],'status':'USABLE',
        'mandatory':False,'selected_by_research_screening':False,
        'reference':{'id':record['id'],'title':record['work'],'author':record['author'],
            'locator':'Structural fixture page 1','original_text':QUOTE,'meaning_mr':PROSE,
            'url':record['primary_url'],'tradition':'Indian'},
        'passage_sha256':record['passage_sha256'],'context_record':context,
        'mapping_limits_mr':[PROSE],'comparative_brief_mr':PROSE,
        'use_constraints':{'max_pair_mappings':1,'max_uses_in_book':1,'book_deduplication_key':record['id'],
            'mandatory_support':False,'score_change_allowed':False,'business_meaning_allowed':False,
            'additional_quoted_words_allowed':0,'main_text_quoted_retelling_allowed':False,
            'quote_whitespace_words':len(QUOTE.split()),'max_quote_whitespace_words':len(QUOTE.split())},
        'eligibility_proof':{'candidate_selection_eligible':True,'research_status':'SUPPORTED',
            'gate_supported_and_reviewed':True,'batch':evidence['batch_id'],
            'request_sha256':evidence['batch_provenance']['request_sha256'],
            'selection_sha256':evidence['batch_provenance']['selection_sha256'],
            'source_hashes':deepcopy(evidence['candidate']['source_hashes'])}}
    menu={'source_catalog_file':runner.SUPPLEMENT_CATALOG,'records':[row]}
    return plan,screening,refs,seal_optional_fixture(catalog,menu)


def seal_optional_fixture(catalog,menu,review_changes=None):
    """Create synthetic exact-byte proof seals; never approve real source files."""
    def proof(value):
        """Encode test JSON exactly; return raw text and matching byte SHA."""
        text=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
        return {'utf8':text,'sha256':runner.preparation.byte_hash(text.encode())}
    catalog_proof=proof(catalog)
    menu=deepcopy(menu);menu['source_catalog_sha256']=catalog_proof['sha256']
    menu_proof=proof(menu)
    review={'verdict':'PASS','menu_sha256':menu_proof['sha256'],
            'catalog_sha256':catalog_proof['sha256'],'approved_ids':[r['id'] for r in menu['records']],
            'approved_mappings':[{'id':r['id'],'pair_id':r['pair_id']} for r in menu['records']],
            'records':[{'id':r['id'],'pair_id':r['pair_id'],'gate':'PASS','issues':[]} for r in menu['records']]}
    review.update(review_changes or {})
    return {'documents':{runner.SUPPLEMENT_CATALOG:catalog_proof,runner.SUPPLEMENT_MENU:menu_proof,
                         runner.SUPPLEMENT_REVIEW:proof(review)}}


def optional_fixture_documents(bundle):
    """Decode synthetic menu/catalog for explicit fault injection; return both."""
    return (json.loads(bundle['documents'][runner.SUPPLEMENT_CATALOG]['utf8']),
            json.loads(bundle['documents'][runner.SUPPLEMENT_MENU]['utf8']))


def test_optional_absent_output_and_baseline_rebuild_are_exact():
    """Absent optional data changes no registry field and permits pure replay."""
    plan,screening,refs=research()
    baseline=runner.build_selection(plan,screening,refs)
    assert baseline==runner.build_selection(plan,screening,refs,optional_supplement=None)
    for e in baseline['entries']:
        assert runner.rebuild_source_packet(e['source_packet'])==e['source_packet']


def test_optional_append_preserves_124_pairs_baseline_proofs_and_model_context():
    """Only the mapped packet gains an optional ref; every baseline field survives."""
    plan,screening,refs,bundle=optional_supplement_fixture(124)
    baseline=runner.build_selection(plan,screening,refs)
    selected=runner.build_selection(plan,screening,refs,optional_supplement=bundle)
    assert len(selected['entries'])==124
    assert selected['coverage']==baseline['coverage']
    for old,new in zip(baseline['entries'],selected['entries']):
        assert old['brief']==new['brief']
        packet=new['source_packet'];assert runner.rebuild_source_packet(packet)==packet
        if new['number']!=1:assert new==old;continue
        prior=old['source_packet']
        assert packet['references'][:-1]==prior['references']
        assert packet['selection_provenance']==prior['selection_provenance']
        assert packet['research_interpretation']==prior['research_interpretation']
        assert packet['examples']==[]
        view=runner.writing_view({'scope':'batch','sources':{'1':packet},'briefs':[new['brief']]})
        context=view['sources']['1']['source_contexts']['MRB-STRUCTURAL-TEST']
        catalog,_=optional_fixture_documents(bundle);record=catalog['records'][0]
        assert context['context_mr']==record['original_devotional_context_mr']
        assert context['source_qualifications']['source_qualifications']['original_limits_mr']==record['limits_mr']
        assert 'optional_supplement_proof' not in view['sources']['1']
        assert context['source_qualifications']['source_qualifications']['optional_not_required'] is True


@pytest.mark.parametrize('fault',['pending','hold','blocker','meaning','context','passage','duplicate',
    'ineligible','override','max_use','quote_cap','extra_ref_field','catalog_path','pair_context',
    'catalog_hash','menu_hash','review_hold','unapproved','missing_review'])
def test_optional_unsafe_or_unreviewed_data_rejected(fault):
    """All declared unsafe variants fail even with synthetic rehashed documents."""
    plan,screening,refs,bundle=optional_supplement_fixture()
    catalog,menu=optional_fixture_documents(bundle);row=menu['records'][0]
    review_changes={}
    if fault=='pending':
        row['status']='OPTIONAL_PENDING_INDEPENDENT_REVIEW';review_changes['verdict']='PENDING'
    elif fault=='hold':catalog['records'][0]['status']='HOLD'
    elif fault=='blocker':catalog['records'][0]['blockers']=['Unresolved source']
    elif fault=='meaning':row['reference']['meaning_mr']+=' बदल'
    elif fault=='context':row['context_record']['original_devotional_context_mr']+=' बदल'
    elif fault=='passage':row['reference']['original_text']+=' बदल'
    elif fault=='duplicate':menu['records'].append(deepcopy(row))
    elif fault=='ineligible':row['pair_id']='N084-S100'
    elif fault=='override':row['id']='N2';row['reference']['id']='N2'
    elif fault=='max_use':row['use_constraints']['max_uses_in_book']=2
    elif fault=='quote_cap':row['use_constraints']['max_quote_whitespace_words']+=1
    elif fault=='extra_ref_field':row['reference']['invented']='extra'
    elif fault=='catalog_path':menu['source_catalog_file']='../escape.json'
    elif fault=='pair_context':row['context_record']['pair_source_contexts']['narada']['meaning_mr']+=' बदल'
    elif fault=='catalog_hash':review_changes['catalog_sha256']='0'*64
    elif fault=='menu_hash':review_changes['menu_sha256']='0'*64
    elif fault=='review_hold':review_changes['verdict']='HOLD'
    elif fault=='unapproved':review_changes['approved_ids']=[]
    bundle=seal_optional_fixture(catalog,menu,review_changes)
    if fault=='missing_review':bundle['documents'].pop(runner.SUPPLEMENT_REVIEW)
    with pytest.raises(ValueError):runner.build_selection(plan,screening,refs,optional_supplement=bundle)


@pytest.mark.parametrize('field',['references','source_contexts','research_interpretation','arbitrary','raw_proof'])
def test_pure_rebuild_rejects_packet_extras_and_drift(field):
    """Consumer cannot accept unchecked extra texts, changed baseline or raw proof."""
    plan,screening,refs,bundle=optional_supplement_fixture()
    packet=runner.build_selection(plan,screening,refs,optional_supplement=bundle)['entries'][0]['source_packet']
    if field=='references':packet['references'][-1]['meaning_mr']+=' बदल'
    elif field=='source_contexts':packet['source_contexts']['MRB-STRUCTURAL-TEST']['context_mr']+=' बदल'
    elif field=='research_interpretation':packet['research_interpretation']['business_extension_mr']+=' बदल'
    elif field=='arbitrary':packet['unchecked_extra']='not allowed'
    else:packet['optional_supplement_proof']['bundle']['documents'][runner.SUPPLEMENT_MENU]['utf8']+=' '
    with pytest.raises(ValueError):runner.rebuild_source_packet(packet)


def test_optional_loader_binds_three_fixed_files_without_cli_flags(tmp_path):
    """Menu presence binds all three exact byte inputs; absence is backward compatible."""
    plan,screening,refs,bundle=optional_supplement_fixture()
    # This tests snapshot I/O; structural source/gate replay is tested above.
    plan['source_hashes']={};seal(plan)
    runner.save(tmp_path/'research-stage-plan.json',plan)
    for name,data in screening.items():
        for kind in ('request','selection','gate'):
            runner.save(tmp_path/'research-screening'/f'{name}-{kind}.json',data[kind])
    baseline=runner.load_selection_inputs(tmp_path)
    assert 'optional_supplement' not in baseline
    for name,proof in bundle['documents'].items():(tmp_path/name).write_bytes(proof['utf8'].encode('utf-8'))
    loaded=runner.load_selection_inputs(tmp_path)
    assert loaded['optional_supplement']==bundle
    for name,proof in bundle['documents'].items():
        assert loaded['input_provenance'][str((tmp_path/name).resolve())]['sha256']==proof['sha256']
    (tmp_path/runner.SUPPLEMENT_REVIEW).unlink()
    with pytest.raises(FileNotFoundError):runner.load_selection_inputs(tmp_path)



def approved_optional_packet(packet):
    """Augment any synthetic researched packet for downstream fake-only tests.

    Input must be a baseline source-only fixture with selection_provenance.
    Return a fully replayable optional packet; no real menu/source is approved.
    """
    evidence=packet['selection_provenance']
    _,_,_,bundle=optional_supplement_fixture(evidence=evidence)
    return runner._append_supplement(packet,bundle,[evidence['candidate']['id']],
                                     {r['id'] for r in packet['references']})


def test_consumer_fixture_supports_different_existing_eligible_pair():
    """Reusable augmentation follows input provenance rather than a fixed pair."""
    plan,screening,refs=research()
    original=runner.build_selection(plan,screening,refs)['entries'][1]['source_packet']
    packet=approved_optional_packet(original)
    assert packet['selection_provenance']['candidate']['id']=='N003-S002'
    assert runner.rebuild_source_packet(packet)==packet


def test_optional_preflight_freezes_inputs_and_blocks_pending_before_keys(options,monkeypatch):
    """Optional documents enter existing bindings and unreviewed use cannot load keys."""
    loader=runner.load_selection_inputs
    inputs=loader(options['input_dir'])
    evidence=next(iter(runner.preparation.research_coverage(inputs['stage_plan'],inputs['screening'])['eligible'].values()))
    _,_,_,bundle=optional_supplement_fixture(evidence=evidence)
    baseline=runner.run(**options)
    def with_optional(path):
        """Return the original frozen test inputs plus explicit optional byte proofs."""
        result=loader(path);result['optional_supplement']=deepcopy(bundle)
        result['input_provenance'].update({str(options['input_dir']/name):{'sha256':proof['sha256']}
                                          for name,proof in bundle['documents'].items()})
        return result
    monkeypatch.setattr(runner,'load_selection_inputs',with_optional)
    augmented=runner.run(**options)
    assert baseline['eligible_count']==augmented['eligible_count']==12
    assert baseline['binding']['inputs']!=augmented['binding']['inputs']
    assert baseline['binding']['selection']!=augmented['binding']['selection']
    catalog,menu=optional_fixture_documents(bundle)
    bundle=seal_optional_fixture(catalog,menu,{'verdict':'HOLD'})
    with pytest.raises(ValueError,match='independent PASS'):
        runner.run(**options,live=True,credentials_dir='must-not-load')



def test_current_exact_pass_review_can_clear_unchanged_pending_menu_label():
    """Never edit/reseal menu merely to change its original pending label."""
    plan,screening,refs,bundle=optional_supplement_fixture()
    catalog,menu=optional_fixture_documents(bundle)
    menu['records'][0]['status']='OPTIONAL_PENDING_INDEPENDENT_REVIEW'
    bundle=seal_optional_fixture(catalog,menu)
    packet=runner.build_selection(plan,screening,refs,optional_supplement=bundle)['entries'][0]['source_packet']
    assert runner.rebuild_source_packet(packet)==packet
    saved=json.loads(packet['optional_supplement_proof']['bundle']['documents'][runner.SUPPLEMENT_MENU]['utf8'])
    assert saved['records'][0]['status']=='OPTIONAL_PENDING_INDEPENDENT_REVIEW'


@pytest.mark.parametrize('fault',['record_hold','mapping','record_missing','record_issue','circular_menu'])
def test_exact_per_record_review_and_non_circular_bindings_required(fault):
    """Top-level PASS cannot cover a held, mismatched or missing record review."""
    plan,screening,refs,bundle=optional_supplement_fixture()
    catalog,menu=optional_fixture_documents(bundle)
    ident=menu['records'][0]['id'];pair=menu['records'][0]['pair_id']
    changes={}
    if fault=='record_hold':changes['records']=[{'id':ident,'pair_id':pair,'gate':'HOLD'}]
    elif fault=='mapping':changes['approved_mappings']=[{'id':ident,'pair_id':'N084-S100'}]
    elif fault=='record_missing':changes['records']=[]
    elif fault=='record_issue':changes['records']=[{'id':ident,'pair_id':pair,'gate':'PASS','issues':['unresolved']}]
    else:menu['review_sha256']='0'*64
    bundle=seal_optional_fixture(catalog,menu,changes)
    with pytest.raises(ValueError):runner.build_selection(plan,screening,refs,optional_supplement=bundle)



def test_v2_priority_preserves_all_124_pairs_packets_and_other_relative_order():
    """Stable priority is scheduling only; no candidate/source/proof is rewritten."""
    plan,screening,refs,bundle=optional_supplement_fixture(124)
    original=runner.build_selection(plan,screening,refs,optional_supplement=bundle)
    chosen=original['entries'][95]['candidate_id']
    prioritized=runner.build_selection(plan,screening,refs,optional_supplement=bundle,pilot_pair_id=chosen)
    before=[e['candidate_id'] for e in original['entries']]
    after=[e['candidate_id'] for e in prioritized['entries']]
    assert after==[chosen]+[i for i in before if i!=chosen]
    assert len(after)==len(set(after))==124
    assert [e['number'] for e in prioritized['entries']]==list(range(1,125))
    packets={e['candidate_id']:e['source_packet'] for e in original['entries']}
    assert all(e['source_packet']==packets[e['candidate_id']] for e in prioritized['entries'])
    assert prioritized['coverage']==original['coverage']
    assert runner.build_selection(plan,screening,refs,optional_supplement=bundle,pilot_pair_id=None)==original
    assert [len(b) for b in runner.book.planned_batches(prioritized['entries'])]==[1]+[10]*12+[3]


@pytest.mark.parametrize('pilot',[True, ['N002-S002'], '', 'N084-S100', 'N78-S28'])
def test_v2_pilot_must_be_exact_eligible_scalar_id(pilot):
    """Reject malformed, absent and unpassed pilot choices before any model use."""
    plan,screening,refs=research()
    with pytest.raises(ValueError,match='pilot_pair_id'):
        runner.build_selection(plan,screening,refs,pilot_pair_id=pilot)


def test_v2_priority_resume_is_exact_and_changed_priority_fails_before_calls(options):
    """New singleton uses the chosen pair; full resume never repeats paid stages."""
    fake=SelectionRegistry()
    chosen='N013-S002'
    pilot=runner.run(**options,pilot_pair_id=chosen,target=1,registry=fake)
    assert pilot['considered']==[chosen]
    assert len(fake.calls)==16
    result=runner.run(**options,pilot_pair_id=chosen,resume=True,registry=fake)
    assert len(result['considered'])==12 and result['considered'][0]==chosen
    assert len(fake.calls)==48
    manifest=runner.load(options['work']/'run-manifest.json')
    assert manifest['version']=='source-only-selection-v2'
    assert len(manifest['binding']['queue'])==64
    runner.run(**options,pilot_pair_id=chosen,resume=True,registry=fake)
    assert len(fake.calls)==48
    with pytest.raises(ValueError,match='Resume bindings'):
        runner.run(**options,pilot_pair_id='N002-S002',resume=True,registry=fake)
    assert len(fake.calls)==48


def test_v2_does_not_resume_a_v1_manifest_or_reuse_its_calls(options):
    """A historical v1 manifest is refused unchanged before provider execution."""
    fake=SelectionRegistry()
    runner.run(**options,target=1,registry=fake)
    path=options['work']/'run-manifest.json'
    manifest=runner.load(path);manifest['version']='source-only-selection-v1'
    runner.save(path,manifest)
    before=path.read_bytes()
    with pytest.raises(ValueError,match='Resume bindings'):
        runner.run(**options,resume=True,target=1,registry=fake)
    assert len(fake.calls)==16 and path.read_bytes()==before


def test_v2_paid_literal_label_preserves_values_and_canonical_ledger(options):
    """Only the model-view key changes; literal values and durable ledger persist."""
    canonical=['चाचणीपुरती मूळ सूत्रनोंद','काल्पनिक दीर्घ ओळ ' * 12,'English audit-only literal']
    runner.save(options['forbidden_path'],canonical)
    fake=SelectionRegistry()
    runner.run(**options,target=1,registry=fake)
    expected=runner.writing_view({'scope':'batch','sources':{},'briefs':[],
                                 'forbidden_originals':canonical})['forbidden_originals']
    for env in envelopes(fake):
        assert 'forbidden_originals' not in env['input']
        assert env['input']['literal_formula_exclusions']==expected
    saved=runner.load(options['work']/'selection-1-discussion.json')
    assert saved['discussion']['_batch']['forbidden_originals']==canonical
    assert runner.load(options['forbidden_path'])==canonical


def test_v2_proposal_and_three_reviews_receive_strongest_actual_reply(options):
    """The latest counterargument survives into arbitration/review without new calls."""
    strongest='Synthetic bounded alternative: preserve source limits; assess the actual ethical choice separately.'
    class CounterargumentRegistry(SelectionRegistry):
        """Expose a distinctive latest reply without claiming semantic calibration."""
        def respond(self,voice,payload):
            """Inspect actual stage context; return unchanged existing response schema."""
            result=super().respond(voice,payload)
            if payload['stage']=='reply' and voice=='narada':
                result['answers']['sutrakar']['1']=strongest
            if payload['stage'] in ('proposal','peer_review'):
                assert payload['discussion']['reply']['narada']['answers']['sutrakar']['1']==strongest
            return result
    fake=CounterargumentRegistry(rejected=(1,))
    result=runner.run(**options,target=1,registry=fake)
    assert result['rejected']==['N002-S002'] and len(fake.calls)==16
    for env in envelopes(fake):
        if env['input']['stage']=='proposal':
            assert 'strongest bounded peer response' in env['instruction']
            assert 'EXISTING derivation (ACCEPT) or rejection_reason (REJECT)' in env['instruction']
            assert 'faithful refinement or alternative yourself' in env['instruction']
        if env['input']['stage']=='peer_review':
            assert 'Audit REJECT as strictly as ACCEPT' in env['instruction']
            assert 'strongest actual peer response was assessed' in env['instruction']
    proposal=runner.load(options['work']/'candidate-001.json')['proposal']
    assert set(proposal)=={'number','decision','rejection_reason'}
    assert 'proposed_sutra' not in proposal


def test_v2_source_method_separates_claims_and_rejects_false_equivalences():
    """Contract regression for the observed RCA; instructions are not semantic proof."""
    system=runner.SELECTION_SYSTEM
    for phrase in ('supplied supplementary relation','qualified modern application',
                   'Absence of literal business language alone is not a veto',
                   'objects, antecedents and limits','unsupported practical promise',
                   'Sutrakar owns the synthesis','THIS new book/run',
                   'literal_formula_exclusions forbids exact/normalized formula copying only',
                   'author/source themes are legitimate inspiration',
                   'REJECT remains legitimate'):
        assert phrase in system
    assert runner.MODELS==runner.book.MODELS
    assert runner.PROVIDERS==runner.book.PROVIDERS
    assert runner.RATES==runner.book.RATES
    assert runner.POLICY['discussion_effort']=='low' and runner.POLICY['timeout_seconds']==240

"""Fake SDK/SQLite exact latest-proposal recovery; production artifacts never written."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest
from scripts import run_source_first_selection as selection
from scripts import adopt_source_first_proposal_recovery as operator
from src.orchestration import source_first_proposal_recovery as recovery
from src.orchestration.research_council import ResearchCouncil, VOICES, _json
from src.orchestration.source_first_provider import SourceFirstProvider
from tests.test_source_first_selection_runner import research, SelectionRegistry


class ProposalRegistry(SelectionRegistry):
    """Generate complete fake native aliases and latest91REJECT without any real SDK."""
    def respond(self, voice, payload):
        """Keep rounds intact; emulate the actual two invalid-ID proposal responses."""
        answer = super().respond(voice,payload)
        if payload['stage'] == 'proposal':
            second = 'repair_feedback' in payload
            rows = []
            for p in answer['proposals']:
                n = p['number']
                if n not in (87,88) and (n != 91 or second):
                    rows.append({'number':n,'decision':'REJECT',
                        'rejection_reason':'हा कृत्रिम चाचणीतील प्रस्ताव स्पष्ट मर्यादित कारणाने नाकारला आहे.'})
                else:
                    packet = payload['sources'][str(n)]
                    p['selected_source_ids'] = packet['source_pair_ids'] + packet['research_interpretation']['evidence_ids']
                    if n == 87:p['proposed_sutra'] = recovery.BEFORE
                    rows.append(p)
            answer['proposals'] = rows
        elif payload['stage'] == 'peer_review':
            # Marker/proof stays server-only; review actual canonical wording.
            assert recovery.MARKER not in json.dumps(payload)
            assert payload['proposal']['proposals'][5]['proposed_sutra'] == recovery.AFTER
        return answer


@pytest.fixture(autouse=True)
def no_live(monkeypatch):
    """Trip on any credential/live construction; all provider calls are explicit fakes."""
    def blocked(*args,**kwargs):
        """An unexpected paid/credential path is a hard test failure."""
        pytest.fail('No live provider or credential access')
    monkeypatch.setattr('scripts.run_source_first_selection.create_live_provider',blocked)
    monkeypatch.setattr('scripts.run_research_book.load_project_credentials',blocked)
    monkeypatch.setattr('src.providers.registry.ProviderRegistry',blocked)


def save(path, value):
    """Write only test-owned JSON and return its exact byte binding."""
    selection.save(path,value)
    return {'path':str(path.resolve()),'sha256':recovery.byte_hash(path)}


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    """Create fourteen fake paid calls, twelve round caches and two FAILED/null rows.

    Independent approval and gates here are synthetic fixtures, not real source
    certification. Packet rebuild is stubbed only for the deliberately doubled
    supplementary fixture; all exact ownership/passage/meaning checks still run.
    """
    plan,screening,refs = research(10)
    entries = selection.build_selection(plan,screening,refs)['entries']
    for n,e in zip(recovery.NUMBERS,entries):e['number']=n;e['brief']['number']=n
    briefs = [e['brief'] for e in entries];briefs[0]['selection_history']=[]
    packets = {str(e['number']):e['source_packet'] for e in entries}
    packet = packets['87'];old = 'EVC-TEST';new = 'EVC-TEST-2';owner=packet['research_interpretation']['candidate_id']
    duplicate = deepcopy(next(ref for ref in packet['references'] if ref['id']==old));duplicate['id']=new
    packet['references'].append(duplicate)
    duplicate = deepcopy(packet['source_contexts'][old]);duplicate.update(id=owner+'::'+new,source_id=new)
    packet['source_contexts'][new]=duplicate
    duplicate=deepcopy(packet['selection_provenance']['research']['selected_evidence'][0]);duplicate['source_id']=new
    packet['selection_provenance']['research']['selected_evidence'].append(duplicate)
    packet['research_interpretation']['evidence_ids'].append(owner+'::'+new)
    monkeypatch.setattr(selection,'rebuild_source_packet',lambda packet:packet)
    source=tmp_path/'src';source.mkdir();binding={'fixture':'a'*64};name='selection-'+'-'.join(map(str,recovery.NUMBERS))
    manifest=save(source/'run-manifest.json',{'binding':binding,'live':False,'budget':30.,'claude_cap':20.,'max_calls':100})
    forbidden=['कृत्रिम चाचणीची आधीची नोंद'];save(source/'selection-1-discussion.json',{'discussion':{'_batch':{'forbidden_originals':forbidden}}})
    policy=__import__('src.orchestration.source_peer_evidence',fromlist=['make_policy']).make_policy([])
    ip=source/(name+'-input.json');ib=save(ip,{'briefs':briefs,'source_packets':packets,'prior_formulas':[],'source_peer_policy':policy})
    pb=save(source/(name+'-peer-policy.json'),{'batch_id':name,'numbers':recovery.NUMBERS,'policy':policy})
    fake=ProposalRegistry();provider=SourceFirstProvider(source/'provider',fake,source_hashes=binding,max_usd=30.,claude_cap_usd=20.,max_calls=100)
    calls=selection.SelectionCalls(provider,source)
    def forbidden_callback(*args,**kwargs):
        """No composition/fifth role or unexpected cached callback may execute."""
        pytest.fail('No additional callback allowed')
    council=ResearchCouncil(source/'council.db',{v:(lambda p,v=v:calls.voice(v,p)) for v in VOICES},
        forbidden_callback,forbidden_callback,source_first_selection=True)
    with pytest.raises(ValueError,match='Exhausted'):
        council.run_batch_discussion(name,briefs,packets,[],forbidden,source_peer_policy=policy)
    dbpath=source/('council.db.batch-'+recovery.digest(name)+'.sqlite3')
    with recovery._ro(dbpath) as db:
        db.row_factory=sqlite3.Row
        attempts=[dict(x) for x in db.execute("SELECT * FROM research_attempts WHERE stage='proposal' ORDER BY attempt")]
        stages=[dict(x) for x in db.execute('SELECT * FROM research_stages ORDER BY stage,speaker')]
    assert len(fake.calls)==14 and len(stages)==12 and all(x['response_json']=='null' for x in attempts)
    monkeypatch.setattr(recovery,'FAILED_CORE',attempts[-1]['request_hash'])
    slot=recovery.digest(['sutrakar','batch/'+name+'/proposal/schema-correction'])
    with recovery._ro(provider.db_path) as db:
        db.row_factory=sqlite3.Row;row=dict(db.execute('SELECT * FROM calls WHERE slot=?',(slot,)).fetchone())
    native=json.loads(row['result_json']);canonical=deepcopy(native);witnesses=[]
    for index,proposal in enumerate(canonical['proposals']):
        if proposal['decision']!='ACCEPT':continue
        packet=packets[str(proposal['number'])]
        for j,alias in enumerate(proposal['selected_source_ids']):
            if j<2:continue
            target,context=next((k,c) for k,c in packet['source_contexts'].items() if c.get('id')==alias)
            ref=next(r for r in packet['references'] if r['id']==target)
            e=next(e for e in packet['selection_provenance']['research']['selected_evidence'] if e['source_id']==target)
            witnesses.append({'json_pointer':f'/proposals/{index}/selected_source_ids/{j}',
                'number':proposal['number'],'owner_candidate_id':context['candidate_id'],'from':alias,'to':target,
                'source_packet_sha256':recovery.digest(packet),'canonical_reference_sha256':recovery.digest(ref),
                'source_context_sha256':recovery.digest(context),'research_evidence_sha256':recovery.digest(e),
                'passage_sha256':e['passage_sha256'],'meaning_sha256':recovery.digest(e['meaning_mr']),
                'context_sha256':recovery.digest(e['context_mr'])})
            proposal['selected_source_ids'][j]=target
    canonical['proposals'][5]['proposed_sutra']=recovery.AFTER
    monkeypatch.setattr(recovery,'NATIVE_HASH',recovery.digest(native));monkeypatch.setattr(recovery,'DERIVED_HASH',recovery.digest(canonical))
    rawref={'path':str((provider.work_dir/'raw'/(slot+'.txt')).resolve()),'sha256':row['raw_sha256']}
    requestpath=source/'peer-evidence'/(slot+'-request.json');requestref={'path':str(requestpath.resolve()),'sha256':recovery.byte_hash(requestpath)}
    design={'schema':'source-first-exact-owned-id-and-one-comma-omission-design-v1',
        'target':{'batch':name,'council_db':str(dbpath.resolve()),'stage':'proposal','speaker':'sutrakar',
            'latest_attempt':2,'core_request_sha256':recovery.FAILED_CORE,'latest_provider_slot':slot},
        'original_bindings':{'input':ib,'policy':pb,'manifest':manifest,'failed_attempts_exact':attempts,
            'cached12_stages':[{'stage':x['stage'],'speaker':x['speaker'],'request_hash':x['request_hash'],
                'response_json_sha256':recovery._text_hash(x['response_json'])} for x in stages],
            'latest_provider_row':row,'latest_raw':rawref,'latest_request_document':requestref},
        'latest_native_parsed_sha256':recovery.NATIVE_HASH,'prospective_canonical_parsed_sha256':recovery.DERIVED_HASH,
        'exact_alias_witnesses':witnesses,'one_comma_omission':{'json_pointer':'/proposals/5/proposed_sutra','number':87,
            'before_exact':recovery.BEFORE,'after_exact':recovery.AFTER,
            'before_utf8_sha256':recovery._text_hash(recovery.BEFORE),'after_utf8_sha256':recovery._text_hash(recovery.AFTER),
            'codepoint_offset_zero_based':11,'codepoint_span_half_open':[11,12],'utf8_byte_span_half_open':[31,32]},
        'all_changed_json_leaves_exact':recovery._changes(native,canonical)}
    approval={'schema':'source-82-91-comma-alias-mechanical-independent-review-v1','gate':'PASS_MECHANICAL_DESIGN_ONLY',
        'chosen_latest_response':{'attempt':2,'provider_slot':slot,'request_sha256':row['request_sha256'],
            'source_sha256':row['source_sha256'],'raw':rawref,'provider_result_sha256':recovery.NATIVE_HASH,
            'native_canonical_sha256':recovery._text_hash(_json(native))},
        'expected_derived_response_canonical_sha256':recovery._text_hash(_json(canonical)),
        'exact_alias_mapping':[{'number':x['number'],'index':int(x['json_pointer'].split('/')[-1]),
            'alias':x['from'],'canonical_id':x['to']} for x in witnesses],
        'single_format_operation':{'number':87,'field':'proposed_sutra','before':recovery.BEFORE,'after':recovery.AFTER,
            'deleted_character':',','original_character_offset_zero_based':11,'deletion_count':1}}
    d=save(tmp_path/'design.json',design);a=save(tmp_path/'approval.json',approval)
    out=operator.prepare(design=d['path'],design_sha256=d['sha256'],approval=a['path'],approval_sha256=a['sha256'],output=tmp_path/'adopt'/'receipt.json')
    gate=tmp_path/'gate.json';save(gate,{'status':'PASS','paid_calls':0,'code_sha256':operator.code_bindings(),
        'tests':[{'path':name,'passed':1,'failed':0,'errors':0} for name in operator.REQUIRED_TESTS]})
    return dict(source=source,council=council,provider=provider,fake=fake,name=name,briefs=briefs,packets=packets,
        forbidden=forbidden,policy=policy,dbpath=dbpath,attempts=attempts,stages=stages,design=design,approval=approval,
        native=native,canonical=canonical,design_ref=d,approval_ref=a,receipt=Path(out['path']),sha=out['sha256'],gate=gate)


def apply(prepared):
    """Apply only to the fake SQLite root through the public gated operator."""
    return operator.apply(receipt=prepared['receipt'],receipt_sha256=prepared['sha'],offline_gate=prepared['gate'])


def test_exact_four_edits_idempotent_adoption_full_cached_rounds_then_three_fresh_peers(prepared):
    """Zero recovery SDK calls preserve FAILED/raw history; only three peers dispatch."""
    p=prepared;count=len(p['fake'].calls);provider_bytes=p['provider'].db_path.read_bytes()
    assert apply(p)['paid_calls']==0 and apply(p)['paid_calls']==0 and len(p['fake'].calls)==count
    assert p['provider'].db_path.read_bytes()==provider_bytes
    with recovery._ro(p['dbpath']) as db:
        db.row_factory=sqlite3.Row
        assert [dict(x) for x in db.execute("SELECT * FROM research_attempts WHERE stage='proposal' ORDER BY attempt")]==p['attempts']
        assert [dict(x) for x in db.execute("SELECT * FROM research_stages WHERE stage!='proposal' ORDER BY stage,speaker")]==p['stages']
    result=p['council'].run_batch_discussion(p['name'],p['briefs'],p['packets'],[],p['forbidden'],source_peer_policy=p['policy'])
    assert len(p['fake'].calls)==count+3
    assert result['proposal']['proposals']==p['canonical']['proposals']
    assert result['rejected_numbers']==[82,83,84,85,86,89,90,91] and result['accepted_numbers']==[87,88]
    p['council'].run_batch_discussion(p['name'],p['briefs'],p['packets'],[],p['forbidden'],source_peer_policy=p['policy'])
    assert len(p['fake'].calls)==count+3


@pytest.mark.parametrize('damage',['marker','table','both','both_and_failed_history','answer','raw','request','receipt'])
def test_mandatory_cache_authority_fails_before_any_sdk_even_if_both_deleted(prepared,damage):
    """The known core binding blocks a forged ordinary-success cache without receipts."""
    p=prepared;apply(p);before=len(p['fake'].calls)
    if damage in ('marker','table','both','both_and_failed_history','answer'):
        with sqlite3.connect(p['dbpath']) as db:
            if damage in ('table','both','both_and_failed_history'):db.execute('DROP TABLE '+recovery.TABLE)
            if damage in ('marker','both','both_and_failed_history','answer'):
                saved=json.loads(db.execute("SELECT response_json FROM research_stages WHERE stage='proposal'").fetchone()[0])
                if damage=='answer':saved['proposals'][9]['rejection_reason']+=' बदल'
                else:saved.pop(recovery.MARKER)
                db.execute("UPDATE research_stages SET response_json=? WHERE stage='proposal'",(_json(saved),))
            if damage=='both_and_failed_history':db.execute("DELETE FROM research_attempts WHERE stage='proposal'")
    elif damage=='raw':(p['provider'].work_dir/'raw'/(p['design']['target']['latest_provider_slot']+'.txt')).write_text('{}',encoding='utf-8')
    elif damage=='request':Path(p['design']['original_bindings']['latest_request_document']['path']).write_text('{}',encoding='utf-8')
    else:p['receipt'].write_text('{}',encoding='utf-8')
    with pytest.raises((ValueError,KeyError)):
        p['council'].run_batch_discussion(p['name'],p['briefs'],p['packets'],[],p['forbidden'],source_peer_policy=p['policy'])
    assert len(p['fake'].calls)==before


@pytest.mark.parametrize('damage',['offset','before_hash','after_hash','extra_space','new_word','unknown_alias',
    'cross_owner','many_to_one','changed_passage','changed_meaning','changed_context','override_pair','older91','latin'])
def test_exact_transformation_rejects_every_extra_edit_or_unattested_alias(prepared,damage):
    """No generalized punctuation stripping, source guessing or favorable older vote."""
    p=prepared;d=deepcopy(p['design']);native=deepcopy(p['native']);packets=deepcopy(p['packets'])
    if damage=='offset':d['one_comma_omission']['codepoint_offset_zero_based']=12
    elif damage in ('before_hash','after_hash'):d['one_comma_omission'][damage.split('_')[0]+'_utf8_sha256']='0'*64
    elif damage=='extra_space':d['one_comma_omission']['after_exact']+=' '
    elif damage=='new_word':native['proposals'][5]['proposed_sutra']=recovery.BEFORE.replace('शीलं','मूल्यं')
    elif damage=='unknown_alias':d['exact_alias_witnesses'][0]['from']='UNKNOWN'
    elif damage=='many_to_one':d['exact_alias_witnesses'][1]['to']=d['exact_alias_witnesses'][0]['to']
    elif damage=='override_pair':d['exact_alias_witnesses'][0]['to']=packets['87']['source_pair_ids'][0]
    elif damage in ('cross_owner','changed_passage','changed_meaning','changed_context'):
        c=packets['87']['source_contexts'][d['exact_alias_witnesses'][0]['to']]
        c[{'cross_owner':'candidate_id','changed_passage':'canonical_passage','changed_meaning':'meaning_mr','changed_context':'context_mr'}[damage]]='FOREIGN'
        d['exact_alias_witnesses'][0]['source_packet_sha256']=recovery.digest(packets['87'])
    elif damage=='older91':native['proposals'][9]=deepcopy(native['proposals'][6]);native['proposals'][9]['number']=91
    else:native['proposals'][6]['proposed_sutra']='business first'
    with pytest.raises((ValueError,KeyError)):recovery.transform(native,packets,d)
    assert len(p['fake'].calls)==14


def test_current_gate_rechecked_under_lock_before_adoption(prepared,monkeypatch):
    """A stale gate introduced after preflight cannot insert a logical success row."""
    p=prepared;original=operator._exclusive
    @contextmanager
    def raced(path):
        """Simulate a concurrent gate change while acquiring the original-source lock."""
        with original(path):
            g=selection.load(p['gate']);g['code_sha256']={};selection.save(p['gate'],g);yield
    monkeypatch.setattr(operator,'_exclusive',raced)
    with pytest.raises(ValueError):apply(p)
    with recovery._ro(p['dbpath']) as db:assert db.execute("SELECT 1 FROM research_stages WHERE stage='proposal'").fetchone() is None
    assert len(p['fake'].calls)==14


@pytest.mark.parametrize('activity',['attempt','stage','provider'])
def test_first_adoption_rejects_any_preexisting_peer_activity(prepared,activity):
    """Only the untouched twelve-round/two-failed-proposal boundary may first adopt."""
    p=prepared
    if activity=='provider':
        slot=recovery.digest(['narada','batch/'+p['name']+'/peer_review'])
        with sqlite3.connect(p['provider'].db_path) as db:
            db.execute('INSERT INTO calls(slot,request_sha256,source_sha256,status) VALUES (?,?,?,?)',
                (slot,'a'*64,'b'*64,'RUNNING'))
    else:
        with sqlite3.connect(p['dbpath']) as db:
            if activity=='attempt':db.execute('INSERT INTO research_attempts VALUES (?,?,?,?,?,?,?,?)',
                (0,'peer_review','narada',1,'a'*64,'RUNNING',None,None))
            else:db.execute('INSERT INTO research_stages VALUES (?,?,?,?,?)',
                (0,'peer_review','narada','a'*64,'{}'))
    with pytest.raises(ValueError,match='pre-existing'):apply(p)
    with recovery._ro(p['dbpath']) as db:
        assert db.execute("SELECT 1 FROM research_stages WHERE stage='proposal'").fetchone() is None
    assert len(p['fake'].calls)==14


def test_alias_only_still_fails_original_shape_and_all_other_fields_equal(prepared):
    """The explicit fourth operation is necessary; lexical/script tests are no grammar waiver."""
    p=prepared;canonical=deepcopy(p['canonical']);canonical['proposals'][5]['proposed_sutra']=recovery.BEFORE
    request={'scope':'batch','entry_numbers':recovery.NUMBERS,'source_first_selection':'source-first-selection-v1','sources_by_entry':p['packets']}
    with pytest.raises(ValueError,match='compound sentences'):_check_alias_only(canonical,request)
    assert len(recovery._changes(p['native'],p['canonical']))==4
    assert [p['number'] for p in p['canonical']['proposals'] if p['decision']=='ACCEPT']==[87,88]


def test_known_spent_core_missing_stage_and_all_history_stops_without_recreation(prepared):
    """Deleting stage, authority and failures cannot reopen the known paid proposal."""
    p=prepared;apply(p);before=len(p['fake'].calls);callbacks=[]
    def forbidden_callback(payload):
        """Observe a forbidden writer callback without ever dispatching a fake SDK."""
        callbacks.append(payload);pytest.fail('Known spent proposal must never call writer')
    p['council'].voices['sutrakar']=forbidden_callback
    with sqlite3.connect(p['dbpath']) as db:
        db.execute("DELETE FROM research_stages WHERE stage='proposal'")
        db.execute('DROP TABLE '+recovery.TABLE)
        db.execute("DELETE FROM research_attempts WHERE stage='proposal'")
    with pytest.raises(ValueError,match='no callback or history recreation'):
        p['council'].run_batch_discussion(p['name'],p['briefs'],p['packets'],[],p['forbidden'],source_peer_policy=p['policy'])
    with recovery._ro(p['dbpath']) as db:
        assert db.execute("SELECT 1 FROM research_attempts WHERE stage='proposal'").fetchone() is None
    assert callbacks==[] and len(p['fake'].calls)==before


def _check_alias_only(answer, request):
    """Invoke unchanged full council validation for the explicit negative shape test."""
    recovery._check_answer('proposal','sutrakar',answer,request)

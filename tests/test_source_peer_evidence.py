"""Offline future peer menu, request identity, literal-row holds and replay tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest
from scripts import run_source_first_selection as s
from src.orchestration import source_peer_evidence as peer
from src.orchestration.source_first_case_capsule import _selection
from tests.test_source_first_selection_runner import research,SelectionRegistry
from tests.test_source_first_book_export import ready
from src.orchestration.independent_review import canonical_hash

COPY='लाभात् पूर्वं मूल्यनिकषः'


def request(numbers=(82,83),voice='researcher',stage='peer_review'):
    """Return a minimal synthetic canonical future request, not a source judgment."""
    return {'number':0,'scope':'batch','batch_id':'selection-'+'-'.join(map(str,numbers)),
        'entry_numbers':list(numbers),'stage':stage,'speaker':voice,peer.KEY:peer.make_policy([]),
        'proposal':{'proposals':[{'number':n,'decision':'REJECT','rejection_reason':'हा मजकूर वर्तमान क्षेत्राशी जुळतो आणि तसेच जतन करावा.'} for n in numbers]},
        'sources':{str(n):{'source_pair_ids':['N2','S2'],'references':[{'id':'N2','original_text':'मूळ पाठ जतन'}],'examples':[]} for n in numbers},
        'briefs':[{'number':n,'selection_history':[{'status':'HOLD_PEER_REVIEW','decision':'HOLD_SENTINEL'}]} for n in numbers],
        'forbidden_originals':['OLD_LITERAL_SENTINEL'],'prior_formulas':['OLD_PRIOR_SENTINEL'],
        'held_selection_decisions':['HOLD_SENTINEL'],'discussion':{'position':{'narada':{'current':'Current peer opinion intact'}}}}


def binding(payload):
    """Extract the exact server-only request/proposal/menu identity for materialization."""
    menu=peer.catalog(payload);return {k:menu[k] for k in ('request_sha256','proposal_sha256','menu_sha256')}


def native(payload):
    """Use existing IDs for literal evidence, with one synthetic reviewer objection."""
    return {'reviews':[{'number':n,'verdict':'REVIEW_REQUIRED','issues':[{'evidence_id':f'P{n:03d}.rejection_reason','reason':'हा चाचणीपुरता स्वतंत्र आक्षेप आहे आणि जतन करावा.','severity':'medium'}]} for n in payload['entry_numbers']]}


@pytest.fixture(autouse=True)
def no_live(monkeypatch):
    """Block all credential/live factories; these tests use only explicit fake providers."""
    def blocked(*args,**kwargs):
        """Any unexpected live construction fails before SDK or key access."""
        pytest.fail('No live source calls or credential access')
    monkeypatch.setattr(s,'create_live_provider',blocked)
    monkeypatch.setattr('scripts.run_research_book.load_project_credentials',blocked)
    monkeypatch.setattr('src.providers.registry.ProviderRegistry',blocked)


def test_mnemonic_ids_select_exact_existing_field_without_regenerating_quote():
    """The canonical quote retains जुळतो exactly; no character correction occurs."""
    payload=request();raw=native(payload);original=deepcopy(raw)
    canonical,audit=peer.materialize(raw,payload,binding(payload))
    assert raw==original and canonical['reviews'][0]['issues'][0]['quote']==payload['proposal']['proposals'][0]['rejection_reason']
    assert 'जुळतो' in canonical['reviews'][0]['issues'][0]['quote']
    assert [r['verdict'] for r in canonical['reviews']]==[r['verdict'] for r in raw['reviews']]
    assert audit[0]['evidence_id']=='P082.rejection_reason'


@pytest.mark.parametrize('damage',['cross_entry','unknown','generated_quote','stale','missing','duplicate','pass_with_issue'])
def test_bad_or_stale_menu_selection_fails_closed(damage):
    """No quote fallback, missing entry, stale binding or fabricated PASS is accepted."""
    payload=request();raw=native(payload);bound=binding(payload)
    if damage=='cross_entry':raw['reviews'][0]['issues'][0]['evidence_id']='P083.rejection_reason'
    elif damage=='unknown':raw['reviews'][0]['issues'][0]['evidence_id']='P999.rejection_reason'
    elif damage=='generated_quote':raw['reviews'][0]['issues'][0]['quote']='जुळते'
    elif damage=='stale':payload['proposal']['proposals'][0]['rejection_reason']+=' बदलले'
    elif damage=='missing':raw['reviews'].pop()
    elif damage=='duplicate':raw['reviews'][1]['number']=82
    else:raw['reviews'][0]['verdict']='PASS'
    with pytest.raises(ValueError):peer.materialize(raw,payload,bound)


@pytest.mark.parametrize('stage',['position','challenge','reply','proposal','peer_review'])
@pytest.mark.parametrize('voice',['narada','shandilya','researcher','sutrakar'])
def test_every_future_paid_voice_omits_old_lists_but_keeps_current_evidence(stage,voice):
    """History projection never redacts current canonical text or current peer opinions."""
    p=request(voice=voice,stage=stage);current=deepcopy(p['discussion'])
    rendered=peer.render(voice,p);view=rendered['payload']['input'];encoded=json.dumps(view,ensure_ascii=False)
    assert 'OLD_LITERAL_SENTINEL' not in encoded and 'OLD_PRIOR_SENTINEL' not in encoded and 'HOLD_SENTINEL' not in encoded
    assert (peer.HISTORY_KEYS-{'prior_accepted_decisions'}).isdisjoint(view) and view['prior_accepted_decisions']==[]
    assert view['discussion']==current and view['sources']['82']['references'][0]['original_text']=='मूळ पाठ जतन'
    assert view['role_focus']==s.ROLE_FOCUS[voice]
    if stage=='peer_review':assert 'quote an exactsubstring' not in rendered['payload']['instruction']


def test_actual_ready_results_are_explicit_committed_cards_and_holds_are_not(tmp_path):
    """Only a real-shaped eligible source result explicitly supplied by parent is included."""
    result=ready(1,'opening');result['draft']['id']='source-selection-N078-S028'
    result['review']['reviewed_draft_sha256']=canonical_hash(result['draft'])
    result['proposal'].update(business_decision_mr='खरे बांधलेले निर्णय क्षेत्र',business_action_mr='खरे बांधलेले कृती क्षेत्र')
    path=tmp_path/'ready.json';s.save(path,result);refs=[{'path':str(path),'sha256':s.byte_hash(path)}]
    policy=peer.make_policy(refs)
    assert policy['committed_cards'][0]['id']=='N078-S028'
    assert policy['committed_cards'][0]['business_action_mr']==result['proposal']['business_action_mr']
    p=request();p[peer.KEY]=policy;view=peer.render('researcher',p)['payload']['input']
    assert view['prior_accepted_decisions']==policy['committed_cards'] and result['draft']['new_sutra'] not in json.dumps(view,ensure_ascii=False)
    with pytest.raises(ValueError):peer.make_policy(refs+refs)
    result['status']='HOLD_PEER_REVIEW';s.save(path,result)
    with pytest.raises(ValueError):peer.make_policy([{'path':str(path),'sha256':s.byte_hash(path)}])


def test_normalized_literal_copy_is_local_but_shared_theme_is_allowed():
    """Only exact normalized text is held; no concept/keyword similarity score exists."""
    policy=peer.make_policy([])
    proposals={'proposals':[{'number':82,'decision':'ACCEPT','proposed_sutra':'लाभात्  पूर्वं मूल्यनिकषः ॥'},
        {'number':83,'decision':'ACCEPT','proposed_sutra':'उद्यमेन विवेकः','topic_mr':'लाभ आणि मूल्यनिकष'}]}
    old=deepcopy(proposals);holds=peer.literal_constraints(proposals,[],[COPY],policy)
    assert set(holds)=={'82'} and proposals==old
    batch={'source_peer_policy':policy,'entry_numbers':[82,83],'prior_formulas':[],'forbidden_originals':[COPY]}
    with pytest.raises(ValueError,match='HOLD_SERVER_CONSTRAINT'):peer.require_entry_clear(82,proposals['proposals'][0],batch)
    peer.require_entry_clear(83,proposals['proposals'][1],batch)


class MenuRegistry(SelectionRegistry):
    """Return native ID reviews with observable unchanged four-model dispatches."""
    def __init__(self,collision=True,bad_once=False):
        """Configure one objective copy or one bounded fake ID failure only."""
        super().__init__();self.collision=collision;self.bad_once=bad_once;self.bad_sent=False
    def respond(self,voice,payload):
        """Consume all current peer maps while rejecting historical-list leakage."""
        if peer.KEY not in payload:return super().respond(voice,payload)
        encoded=json.dumps(payload,ensure_ascii=False)
        assert 'OLD_LITERAL_SENTINEL' not in encoded and 'held_selection_decisions' not in payload and 'prior_formulas' not in payload
        value=super().respond(voice,payload)
        if payload['stage']=='proposal' and self.collision:value['proposals'][0]['proposed_sutra']=COPY
        if payload['stage']=='peer_review' and self.bad_once and voice=='researcher' and not self.bad_sent:
            self.bad_sent=True;value['reviews'][0].update(verdict='REVIEW_REQUIRED',issues=[{'evidence_id':'P999.rejection_reason','reason':'चाचणीपुरता नोंदवलेला आक्षेप येथे असतो','severity':'medium'}])
        return value


@pytest.fixture
def setup(tmp_path,monkeypatch):
    """Isolate the actual runner's future82..91 batch; earlier81 fake entries need no calls."""
    plan,screening,refs=research(91);directory=tmp_path/'inputs';directory.mkdir()
    s.save(directory/'research-stage-plan.json',plan);refpath=directory/'refs.json';s.save(refpath,refs)
    forbidden=directory/'forbidden.json';s.save(forbidden,[COPY,'OLD_LITERAL_SENTINEL'])
    monkeypatch.setattr(s,'code_bindings',lambda:{'future-fixture':'a'*64})
    gate=directory/'gate.json';s.save(gate,{'status':'PASS','paid_calls':0,'code_sha256':s.code_bindings(),
        'tests':[{'path':p,'passed':1,'failed':0,'errors':0} for p in s.REQUIRED_TESTS]})
    monkeypatch.setattr(s,'require_validator_calibration',lambda p:{'status':'PASS','fixture':True})
    monkeypatch.setattr(s,'load_selection_inputs',lambda p:{'stage_plan':deepcopy(plan),'screening':deepcopy(screening),
        'input_provenance':{str(directory/'research-stage-plan.json'):{'sha256':s.byte_hash(directory/'research-stage-plan.json')}}})
    # Test-only scheduling isolates the next wholly unstarted original10-entry batch.
    # Production still uses the unchanged singleton+10 full124 queue.
    monkeypatch.setattr(s.book,'planned_batches',lambda entries:[entries[81:91]])
    return dict(input_dir=directory,research_plan_sha256=s.byte_hash(directory/'research-stage-plan.json'),pair_references_path=refpath,
        pair_references_sha256=s.byte_hash(refpath),forbidden_path=forbidden,offline_gate=gate,calibration_dir=directory/'calibration',
        work=tmp_path/'source',target=91,budget=100.,claude_cap=80.,max_calls=100,
        source_peer_policy=peer.VERSION,committed_references=[],narada_peer_output_tokens=16384,narada_thinking_level='MEDIUM')


def test_one_copy_nine_valid_retained_all_peer_calls_and_zero_sdk_resume(setup):
    """A known per-entry collision cannot strand nine valid proposals or rewrite opinions."""
    registry=MenuRegistry();report=s.run(**setup,registry=registry)
    assert len(registry.calls)==16 and len(report['accepted'])==9 and len(report['held_server_constraint'])==1
    work=Path(setup['work']);collision=s.load(work/'candidate-082.json')
    assert collision['status']=='HOLD_SERVER_CONSTRAINT' and collision['case_curation_eligible'] is False
    assert collision['proposal']['decision']=='ACCEPT' and all(r['verdict']=='PASS' for r in collision['peer_review'].values())
    for n in range(83,92):assert s.load(work/f'candidate-{n:03d}.json')['case_curation_eligible'] is True
    bundle=s.load(work/collision['discussion_file']);sup=s.load(work/collision['discussion_file'].replace('-discussion.json','-input.json'))
    assert len(bundle['proposal']['proposals'])==10 and len(bundle['peer_review'])==3
    with pytest.raises(ValueError,match='HOLD_SERVER_CONSTRAINT'):
        _selection(82,sup['briefs'][0],sup['source_packets']['82'],bundle['discussion'],bundle['proposal'],bundle['peer_review'])
    _selection(83,sup['briefs'][1],sup['source_packets']['83'],bundle['discussion'],bundle['proposal'],bundle['peer_review'])
    before=len(registry.calls);s.run(**setup,registry=registry,resume=True)
    assert len(registry.calls)==before
    accepted=work/'candidate-083.json';policy=peer.make_policy([{'path':str(accepted),'sha256':s.byte_hash(accepted)}])
    assert policy['committed_cards'][0]['number']==83
    with pytest.raises(ValueError):peer.make_policy([{'path':str(work/'candidate-082.json'),'sha256':s.byte_hash(work/'candidate-082.json')}])


def test_existing_bounded_invalid_id_protocol_preserves_raw_then_replays(setup):
    """One native bad reference is retained; only the existing second schema slot is used."""
    registry=MenuRegistry(collision=False,bad_once=True);s.run(**setup,registry=registry)
    assert len(registry.calls)==17
    work=Path(setup['work']);name='selection-'+'-'.join(map(str,range(82,92)))
    path=work/('council.db.batch-'+hashlib.sha256(json.dumps(name,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()+'.sqlite3')
    with peer._ro(path) as db:
        rows=db.execute("SELECT state,response_json FROM research_attempts WHERE stage='peer_review' AND speaker='researcher' ORDER BY attempt").fetchall()
    assert [r[0] for r in rows]==['FAILED','COMPLETE'] and 'P999.rejection_reason' in rows[0][1]
    s.run(**setup,registry=registry,resume=True);assert len(registry.calls)==17


@pytest.mark.parametrize('damage',['mapping','raw','stage_marker','request_document','attempt'])
def test_future_cache_mapping_is_mandatory_before_any_new_sdk(setup,damage):
    """Cached canonical field text is never trusted without native/request/menu proof."""
    registry=MenuRegistry(collision=False);s.run(**setup,registry=registry);work=Path(setup['work'])
    bundle=s.load(work/s.load(work/'candidate-083.json')['discussion_file']);pointer=bundle['peer_review']['researcher'][peer.MAPPING];proof=s.load(pointer['path'])
    dbpath=Path(bundle['checkpoint_path'])
    if damage=='mapping':
        proof['canonical_sha256']='f'*64;s.save(pointer['path'],proof)
    elif damage=='raw':(work/'provider/raw'/(proof['provider_row']['slot']+'.txt')).write_text('{}',encoding='utf-8')
    elif damage=='request_document':
        call=s.load(proof['request_document']['path']);call['payload']['input']['proposal_evidence_menu']['items'][0]['field']='changed';s.save(proof['request_document']['path'],call)
    else:
        with sqlite3.connect(dbpath) as db:
            if damage=='attempt':db.execute("UPDATE research_attempts SET response_json='{}' WHERE stage='peer_review' AND speaker='researcher'")
            else:
                row=db.execute("SELECT response_json FROM research_stages WHERE stage='peer_review' AND speaker='researcher'").fetchone();value=json.loads(row[0]);value.pop(peer.MAPPING)
                db.execute("UPDATE research_stages SET response_json=? WHERE stage='peer_review' AND speaker='researcher'",(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')),))
    before=len(registry.calls)
    with pytest.raises(Exception):s.run(**setup,registry=registry,resume=True)
    assert len(registry.calls)==before


def test_new_policy_rejects_started_legacy_batch_before_provider(setup):
    """No opt-in can reinterpret any already saved legacy input or paid slot."""
    work=Path(setup['work']);work.mkdir();name='selection-'+'-'.join(map(str,range(82,92)))
    s.save(work/(name+'-input.json'),{'legacy':True})
    with pytest.raises(ValueError,match='started'):peer.batch_policy(work,name,list(range(82,92)),peer.VERSION,[],create=False)
    with pytest.raises(ValueError):peer.validate_policy(peer.make_policy([]),[81])

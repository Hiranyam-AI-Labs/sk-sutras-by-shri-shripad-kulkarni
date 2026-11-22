"""Fake-only grouped revision menus and real-shaped recovered87/88 lineage."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest
from scripts import run_source_first_revision_menu as menu
from scripts import run_source_first_selected_book as selected
from tests.test_source_first_revision_batch import options as legacy_options
from tests.test_source_first_revision_runner import snapshot
from tests.test_source_first_book_runner import Registry
from tests.test_source_first_book_export import ready
from tests.test_source_first_case_capsule import build_case_capsule, case_work
from src.orchestration.source_first_case_capsule import _selection
from tests.test_source_first_proposal_recovery import prepared as recovery_prepared, apply as recovery_apply
from src.orchestration.independent_review import canonical_hash


class MenuRegistry(Registry):
    """Return only four bounded fake outputs; canonical IDs and native peer IDs."""
    def __init__(self, reject=(), hold=(), collision=False, bad_id=False, alias=False, missing=False):
        """Configure one-shot dispositions or faults, never a model retry loop."""
        super().__init__();self.reject=set(reject);self.hold=set(hold)
        self.collision=collision;self.bad_id=bad_id;self.alias=alias;self.missing=missing
    def respond(self, voice, payload):
        """Inspect paid current context without old comparator lists or proof inventories."""
        assert payload['stage'] in ('proposal','peer_review') and voice!='validator'
        assert not {'prior_formulas','held_selection_decisions','revision_history','literal_formula_exclusions','forbidden_originals'} & payload.keys()
        assert len(payload['prior_accepted_decisions'])==6
        assert all(set(x)=={'id','number','business_decision_mr','business_action_mr'} for x in payload['prior_accepted_decisions'])
        assert set(payload['discussion'])=={'position','challenge','reply'}
        assert payload['role_focus']==menu.r.selection.ROLE_FOCUS[voice]
        for stage,field in [('position','positions'),('challenge','challenges'),('reply','answers')]:
            assert set(payload['discussion'][stage])==set(menu.r.VOICES)
            for row in payload['discussion'][stage].values():
                maps=[row[field]] if stage=='position' else row[field].values()
                assert all(set(cells)=={str(n) for n in payload['entry_numbers']} for cells in maps)
        for packet in payload['sources'].values():
            assert all('::' not in ref['id'] for ref in packet['references'])
            assert not any('::' in x for x in packet['research_interpretation'].get('evidence_ids',[]))
        numbers=payload['entry_numbers'];refs=payload['canonical_reference_menu']['entries']
        if payload['stage']=='proposal':
            proposals=[]
            for n in numbers:
                if n in self.reject:
                    p={'number':n,'decision':'REJECT','rejection_reason':'कृत्रिम चाचणीत मूळ दोन्ही स्रोतांचा संबंध अपुरा असल्याने नकार दिला आहे'}
                else:
                    p=deepcopy(payload['original_proposals'][str(n)])
                    p['proposed_sutra']={0:'सत्येन व्यवहारः',1:'विवेकेन कर्म',2:'प्रमाणेन निर्णयः',3:'निष्ठया सेवा'}[n%4]
                    if self.collision and n==numbers[0]:p['proposed_sutra']='आदौ शुद्धमर्यादा स्थाप्या'
                    p['derivation']='Synthetic revised source relation; qualified modern application retained for test only'
                    p['selected_source_ids']=list(refs[str(n)]['required_source_pair_ids'])+[refs[str(n)]['supplementary_reference_ids'][0]]
                    if self.alias and n==numbers[0]:p['selected_source_ids'][-1]='FOREIGN::'+p['selected_source_ids'][-1]
                proposals.append(p)
            responses=[{'issue_id':i['issue_id'],'disposition':'CONTESTED',
                'reason_mr':'या कृत्रिम चाचणीत मूळ शब्दांकन आणि खरा स्रोतसंबंध स्वतंत्रपणे तपासला आहे'} for i in payload['original_peer_issues']]
            return {'proposals':proposals[:-1] if self.missing else proposals,'revision_responses':responses}
        rows=[]
        for p in payload['proposal']['proposals']:
            n=p['number'];assert payload['current_formula_shapes'][str(n)]==menu.r.formula_shape(p)
            row={'number':n,'verdict':'PASS','issues':[]}
            if voice=='researcher' and (n in self.hold or self.bad_id):
                row.update(verdict='REVIEW_REQUIRED',issues=[{'evidence_id':('P999.derivation' if self.bad_id else f'P{n:03d}.derivation'),
                    'reason':'Synthetic substantive source concern remains, not a missing-label premise','severity':'medium'}])
            rows.append(row)
        return {'reviews':rows}


class BlindRegistry(MenuRegistry):
    """Use original context only as Sutrakar; fresh peers see a current-only allowlist."""
    def __init__(self, missing=(2,), reported=False):
        """Configure blocking missingness or an actually reported diagnostic value."""
        super().__init__();self.missing_numbers=set(missing);self.reported=reported;self.peer_views={};self.writer_view=None
    def respond(self,voice,payload):
        """Assert blinding and emit raw judgments, never classify unknown severity."""
        if payload['stage']=='proposal':
            self.writer_view=deepcopy(payload)
            assert payload['original_peer_issues'] and payload['discussion'] and payload['original_proposals']
            return super().respond(voice,payload)
        self.peer_views[voice]=deepcopy(payload)
        assert set(payload)=={'number','scope','batch_id','entry_numbers','stage','speaker','sources','proposal',
            'prior_accepted_decisions','current_formula_shapes','canonical_reference_menu','menu_policy','role_focus','proposal_evidence_menu'}
        assert not any(k in payload for k in ('discussion','original_peer_issues','original_proposals','original_peer_reviews','revision_responses'))
        assert len(payload['prior_accepted_decisions'])==6
        for packet in payload['sources'].values():assert 'research_interpretation' not in packet
        rows=[]
        for p in payload['proposal']['proposals']:
            n=p['number'];row={'number':n,'verdict':'PASS','issues':[]}
            assert payload['current_formula_shapes'][str(n)]==menu.r.formula_shape(p)
            if voice=='shandilya' and n in self.missing_numbers:
                issue={'evidence_id':f'P{n:03d}.derivation','reason':'Synthetic substantive remaining source limitation unchanged'}
                if self.reported:issue['severity']='medium'
                row.update(verdict='REVIEW_REQUIRED',issues=[issue])
            rows.append(row)
        return {'reviews':rows}


@pytest.fixture(autouse=True)
def no_live(monkeypatch):
    """Refuse any credential or live registry path, including negative tests."""
    def blocked(*args,**kwargs):
        """An unexpected nonfake provider construction is a hard test failure."""
        pytest.fail('No live API/credentials allowed')
    monkeypatch.setattr(menu.r,'create_live_provider',blocked)
    monkeypatch.setattr('scripts.run_research_book.load_project_credentials',blocked)
    monkeypatch.setattr('src.providers.registry.ProviderRegistry',blocked)


def add_menu_inputs(options,tmp_path,monkeypatch):
    """Attach six synthetic READY bindings and a current two-file adapter gate."""
    refs=[]
    for index,n in enumerate(menu.COMMITTED_NUMBERS,1):
        result=ready(n,'opening');result['draft']['id']=f'source-selection-N{index:03d}-S001'
        result['draft']['new_sutra']='आदौ शुद्धमर्यादा स्थाप्या'
        result['review']['reviewed_draft_sha256']=canonical_hash(result['draft'])
        result['proposal'].update(business_decision_mr='कृत्रिम पूर्वनिर्धारित मर्यादित निर्णय येथे जतन आहे',
            business_action_mr='कृत्रिम पूर्वनिर्धारित मर्यादित कृती येथे जतन आहे')
        path=tmp_path/f'ready-{n}.json';menu.r.save(path,result)
        refs.append({'path':str(path),'sha256':menu.r.byte_hash(path)})
    options['committed_results']=refs;options['evidence_menu']=True
    gate=tmp_path/'menu-gate.json';menu.r.save(gate,{'status':'PASS','paid_calls':0,'code_sha256':menu.code_bindings(),
        'tests':[{'path':menu.TEST,'passed':1,'failed':0,'errors':0}]})
    options['menu_gate']=gate
    return options


@pytest.fixture
def options(tmp_path,monkeypatch):
    """Reuse real fake-source journal/DB fixtures, with original two HOLDs only."""
    values=legacy_options.__wrapped__(tmp_path,monkeypatch)
    monkeypatch.setattr(menu,'ALLOWED_NUMBERS',frozenset((2,3,4,5)))
    values['work']=tmp_path/'menu';return add_menu_inputs(values,tmp_path,monkeypatch)


@pytest.fixture
def recovered_options(tmp_path,monkeypatch):
    """Build actual fake recovery authority + three native-ID peer proofs for87/88."""
    p=recovery_prepared.__wrapped__(tmp_path,monkeypatch);recovery_apply(p)
    previous=p['fake'].respond
    def held_reviews(voice,payload):
        """Create real fake reviewer objections about the actual canonical proposal."""
        answer=previous(voice,payload)
        if payload['stage']=='peer_review' and voice=='researcher':
            for row in answer['reviews']:
                if row['number'] in (87,88):row.update(verdict='REVIEW_REQUIRED',issues=[{
                    'evidence_id':f"P{row['number']:03d}.derivation",'reason':'Synthetic original substantive source concern', 'severity':'medium'}])
        return answer
    p['fake'].respond=held_reviews
    bundle=p['council'].run_batch_discussion(p['name'],p['briefs'],p['packets'],[],p['forbidden'],source_peer_policy=p['policy'])
    discussion=p['source']/(p['name']+'-discussion.json');menu.r.save(discussion,bundle)
    for n in (87,88):
        proposal=next(x for x in bundle['proposal']['proposals'] if x['number']==n)
        peers={v:next(x for x in review['reviews'] if x['number']==n) for v,review in bundle['peer_review'].items()}
        brief=next(b for b in p['briefs'] if b['number']==n)
        menu.r.save(p['source']/f'candidate-{n:03d}.json',{'number':n,'candidate_id':brief['candidate_id'],
            'proposal':proposal,'peer_review':peers,'discussion_file':discussion.name,
            'discussion_sha256':menu.r.byte_hash(discussion),'selection_entry_hash':bundle['discussion']['_batch']['entry_hashes'][str(n)],
            'source_packet_sha256':menu.r.selection.preparation.digest(p['packets'][str(n)]),
            'status':'HOLD_PEER_REVIEW','case_curation_eligible':False,'composition_approved':False})
    # Only the legacy external execution-gate receipt is stubbed for fixture wiring.
    monkeypatch.setattr(menu.r,'code_bindings',lambda:{'base-fixture':'b'*64})
    basegate=tmp_path/'revision-gate.json';menu.r.save(basegate,{'status':'PASS','paid_calls':0,'code_sha256':menu.r.code_bindings(),
        'tests':[{'path':n,'passed':1,'failed':0,'errors':0} for n in menu.r.REQUIRED_TESTS]})
    bg=tmp_path/'batch-gate.json';menu.r.save(bg,{'status':'PASS','paid_calls':0,'code_sha256':menu.batch.code_bindings(),
        'tests':[{'path':menu.batch.TEST,'passed':1,'failed':0,'errors':0}]})
    result={'source_dir':p['source'],'numbers':[87,88],
        'candidate_sha256':{str(n):menu.r.byte_hash(p['source']/f'candidate-{n:03d}.json') for n in (87,88)},
        'input_sha256':menu.r.byte_hash(p['source']/(p['name']+'-input.json')),
        'discussion_sha256':menu.r.byte_hash(discussion),'offline_gate':basegate,'batch_gate':bg,
        'work':tmp_path/'rm','budget':4.,'claude_cap':3.,'max_calls':4}
    return add_menu_inputs(result,tmp_path,monkeypatch)


def test_four_calls_exact_menus_proof_capsule_consumer_and_zero_resume(options,tmp_path):
    """Real fake stages preserve old journals, materialize exact fields and feed existing consumers."""
    before=snapshot(options['source_dir']);fake=MenuRegistry();result=menu.run(**options,registry=fake)
    assert len(fake.calls)==4 and result['composition_calls']==result['validator_calls']==0
    derived=menu.r.load(options['work']/result['discussion']['path'])
    original=menu.r.load(options['source_dir']/result['discussion']['path'])
    assert derived['discussion']==original['discussion']
    assert [p for p in derived['proposal']['proposals'] if p['number'] not in (2,3)]==[p for p in original['proposal']['proposals'] if p['number'] not in (2,3)]
    for voice in menu.r.VOICES[:-1]:
        stage=menu.r.load(options['work']/f'peer_review-{voice}.json')
        assert stage['native']==stage['canonical'] and stage['evidence_mapping']['model_opinions_unchanged']
    supplied=menu.r.load(options['work']/result['input']['path']);pool=case_work(tmp_path/'cases')
    capsule=build_case_capsule(number=2,brief=next(b for b in supplied['briefs'] if b['number']==2),sources=supplied['source_packets']['2'],
        discussion=derived['discussion'],proposal=derived['proposal'],peer_review=derived['peer_review'],case_work_dir=pool,
        used_case_ids=set(),used_identity_keys=set(),case_slots=[{'kind':kind,'case_id':ident,
            'fit_reason_mr':'कृत्रिम चाचणीत मर्यादित तथ्याधारित उपयोग तपासला आहे','limitations_mr':'ही वास्तविक तथ्यपुष्टी नाही'}
            for kind,ident in [('positive','positive-a'),('caution','caution-b')]])
    task={'number':2,'brief':next(b for b in supplied['briefs'] if b['number']==2),'source_packet':supplied['source_packets']['2'],'case_capsule':capsule}
    for key,path in [('selection_input',options['work']/result['input']['path']),('selection_discussion',options['work']/result['discussion']['path']),('candidate_record',options['work']/'candidate-002.json')]:
        task[key]={'path':str(path),'sha256':menu.r.byte_hash(path)}
    assert selected.validate_task(task,tmp_path,set(),set())['proposal']['decision']=='ACCEPT'
    saved=(options['work']/'result.json').read_bytes();assert menu.run(**options,registry=fake,resume=True)['new_calls']==0
    assert len(fake.calls)==4 and (options['work']/'result.json').read_bytes()==saved and snapshot(options['source_dir'])==before


def test_recovered_87_88_full_original_authority_and_native_peer_lineage(recovered_options):
    """Verify recovery/ID receipts, reuse twelve rounds, keep old proofs on old wording only."""
    o=recovered_options;before=snapshot(o['source_dir']);fake=MenuRegistry(hold=(88,))
    result=menu.run(**o,registry=fake);assert len(fake.calls)==4
    assert [x['status'] for x in result['candidates']]==['ACCEPTED_FOR_CASE_ASSIGNMENT','HOLD_PEER_REVIEW']
    old=menu.r.load(o['source_dir']/result['discussion']['path']);new=menu.r.load(o['work']/result['discussion']['path'])
    assert new['discussion']==old['discussion'] and menu.recovery.MARKER in old['proposal'] and menu.recovery.MARKER not in new['proposal']
    provenance=menu.r.load(o['work']/'revision-provenance.json')
    assert provenance['original_stage_envelopes_exact']=={'proposal':old['proposal'],'peer_review':old['peer_review']}
    stage=menu.r.load(o['work']/'peer_review-researcher.json')
    native=next(r for r in stage['native']['reviews'] if r['number']==88);canonical=next(r for r in stage['canonical']['reviews'] if r['number']==88)
    assert native['issues'][0]['evidence_id']=='P088.derivation' and canonical['issues'][0]['quote']==next(p['derivation'] for p in new['proposal']['proposals'] if p['number']==88)
    assert native['verdict']==canonical['verdict']=='REVIEW_REQUIRED' and native['issues'][0]['reason']==canonical['issues'][0]['reason']
    assert next(p for p in new['proposal']['proposals'] if p['number']==91)==next(p for p in old['proposal']['proposals'] if p['number']==91)
    assert menu.run(**o,registry=fake,resume=True)['new_calls']==0 and len(fake.calls)==4 and snapshot(o['source_dir'])==before


def test_four_original_holds_remain_one_bounded_group(options):
    """The original four-entry group uses four calls, not four separate councils."""
    options.update(numbers=[2,3,4,5],candidate_sha256={str(n):menu.r.byte_hash(options['source_dir']/f'candidate-{n:03d}.json') for n in (2,3,4,5)})
    fake=MenuRegistry();result=menu.run(**options,registry=fake)
    assert len(fake.calls)==4 and len(result['candidates'])==4
    assert all(c['status']=='ACCEPTED_FOR_CASE_ASSIGNMENT' for c in result['candidates'])
    for voice in menu.r.VOICES:
        kind='proposal' if voice=='sutrakar' else 'peer_review'
        document=menu.r.load(options['work']/f'request-{kind}-{voice}.json')
        assert document['max_output_tokens']==(16384 if voice=='narada' else 10000)
        assert document['generation_options']==({'thinking_level':'MEDIUM'} if voice=='narada' else {})
        if menu.r.selection.PROVIDERS[voice]=='anthropic':assert document['adapter_effort']=='medium'


def test_reject_and_held_outputs_are_considered_but_never_advance(options):
    """A substantive rejection needs no formula; unresolved actual peer feedback stays HOLD."""
    fake=MenuRegistry(reject=(2,),hold=(3,));result=menu.run(**options,registry=fake)
    assert len(fake.calls)==4 and [c['status'] for c in result['candidates']]==['REJECTED','HOLD_PEER_REVIEW']
    rejected=menu.r.load(options['work']/'candidate-002.json')
    assert 'proposed_sutra' not in rejected['proposal'] and rejected['case_curation_eligible'] is False


def test_peer_contract_whole_field_remaining_defect_counts_are_not_grammar_pass():
    """Clarity prevents false missing-label/count premises without dismissing true issues."""
    for phrase in ('WHOLE field','actual remaining','counts are NOT grammar PASS',
        'label is NOT proof','legitimate application/evidence limits','No automatic acceptance'):
        assert phrase in menu.PEER
    assert 'Both canonical sources need a substantive positive role' in menu.SYSTEM
    assert 'reject rather than inventing a connection' in menu.SYSTEM


@pytest.mark.parametrize('fault',['stale','cross_entry','quote','missing','duplicate','pass_issue'])
def test_field_menu_is_owner_bound_exact_and_never_repairs_native_opinions(fault):
    """Pure ID materialization rejects tamper without model dispatch or guessed text."""
    request={'scope':'batch','entry_numbers':[87,88],'speaker':'researcher','proposal':{'proposals':[
        {'number':n,'decision':'REJECT','rejection_reason':'हा विद्यमान पूर्ण चाचणी मजकूर जसाच्या तसा जतन करावा'} for n in (87,88)]}}
    native={'reviews':[{'number':n,'verdict':'REVIEW_REQUIRED','issues':[{'evidence_id':f'P{n:03d}.rejection_reason',
        'reason':'Existing synthetic source concern unchanged','severity':'medium'}]} for n in (87,88)]}
    original=deepcopy(native);catalog=menu.catalog(request);binding={k:catalog[k] for k in ('request_sha256','proposal_sha256','menu_sha256')}
    canonical,proof=menu.materialize(native,request,binding)
    assert native==original and canonical['reviews'][0]['issues'][0]['quote']==request['proposal']['proposals'][0]['rejection_reason']
    assert proof['model_opinions_unchanged'] is True
    if fault=='stale':request['proposal']['proposals'][0]['rejection_reason']+=' बदल'
    elif fault=='cross_entry':native['reviews'][0]['issues'][0]['evidence_id']='P088.rejection_reason'
    elif fault=='quote':native['reviews'][0]['issues'][0]['quote']='invented'
    elif fault=='missing':native['reviews'].pop()
    elif fault=='duplicate':native['reviews'][1]['number']=87
    else:native['reviews'][0]['verdict']='PASS'
    with pytest.raises(ValueError):menu.materialize(native,request,binding)


@pytest.mark.parametrize('fault',['recovery_marker','peer_marker','peer_native_raw','council_stage'])
def test_recovered_original_proof_tamper_refused_before_new_calls(recovered_options,fault):
    """Bound materialized files alone never replace original recovered/native checkpoints."""
    o=recovered_options;c=menu.r.load(o['source_dir']/'candidate-087.json');bundle=menu.r.load(o['source_dir']/c['discussion_file'])
    if fault=='peer_native_raw':
        pointer=bundle['peer_review']['researcher'][menu.source_menu.MAPPING];proof=menu.r.load(pointer['path'])
        (o['source_dir']/'provider/raw'/(proof['provider_row']['slot']+'.txt')).write_text('{}',encoding='utf-8')
    else:
        with sqlite3.connect(bundle['checkpoint_path']) as db:
            if fault=='council_stage':db.execute("DELETE FROM research_stages WHERE stage='reply' AND speaker='narada'")
            else:
                stage,voice,key=('proposal','sutrakar',menu.recovery.MARKER) if fault=='recovery_marker' else ('peer_review','researcher',menu.source_menu.MAPPING)
                row=db.execute('SELECT response_json FROM research_stages WHERE stage=? AND speaker=?',(stage,voice)).fetchone();value=json.loads(row[0]);value.pop(key)
                db.execute('UPDATE research_stages SET response_json=? WHERE stage=? AND speaker=?',(menu.r._json(value),stage,voice))
    fake=MenuRegistry()
    with pytest.raises(ValueError):menu.run(**o,registry=fake)
    assert fake.calls==[] and not o['work'].exists()


def test_one_literal_collision_does_not_strand_other_row_or_rewrite_votes(options):
    """One copied formula stays server-held despite actual threePASS; other output advances."""
    fake=MenuRegistry(collision=True);result=menu.run(**options,registry=fake)
    assert len(fake.calls)==4 and [c['status'] for c in result['candidates']]==['HOLD_SERVER_CONSTRAINT','ACCEPTED_FOR_CASE_ASSIGNMENT']
    held=menu.r.load(options['work']/'candidate-002.json')
    assert held['proposal']['decision']=='ACCEPT' and all(p['verdict']=='PASS' for p in held['peer_review'].values()) and held['case_curation_eligible'] is False


@pytest.mark.parametrize('fault',['bad_id','alias','missing'])
def test_bad_native_output_is_terminal_no_auto_retry(options,fault):
    """Unknown IDs/aliases or incomplete proposals retain reservations and stop permanently."""
    fake=MenuRegistry(**{fault:True})
    with pytest.raises(menu.r.SourceFirstStopped):menu.run(**options,registry=fake)
    count=len(fake.calls);assert count==(4 if fault=='bad_id' else 1)
    assert menu.r.load(options['work']/'report.json')['reservation_usd']>0
    with pytest.raises(menu.r.SourceFirstStopped):menu.run(**options,registry=fake,resume=True)
    assert len(fake.calls)==count


@pytest.mark.parametrize('damage',['mapping','request','raw','stage','receipt'])
def test_revision_cache_requires_exact_native_mapping_before_dispatch(options,damage):
    """Raw/request/mapping/firstreceipt changes fail rather than recreate a success."""
    fake=MenuRegistry(hold=(3,));menu.run(**options,registry=fake)
    path=options['work']/'peer_review-researcher.json';proof=menu.r.load(path)
    if damage=='mapping':proof['evidence_mapping']['canonical_sha256']='0'*64;menu.r.save(path,proof)
    elif damage=='stage':path.unlink()
    elif damage=='request':(options['work']/'request-peer_review-researcher.json').write_text('{}',encoding='utf-8')
    elif damage=='receipt':(options['work']/proof['first_validation_receipt']['path']).write_text('{}',encoding='utf-8')
    else:(options['work']/'provider/raw'/(proof['provider']['slot']+'.txt')).write_text('{}',encoding='utf-8')
    count=len(fake.calls)
    with pytest.raises(menu.r.SourceFirstStopped):menu.run(**options,registry=fake,resume=True)
    assert len(fake.calls)==count


def test_explicit_scope_gates_and_pure_preflight(options):
    """No execution root or constructor before opt-in, complete gates and READY proof."""
    assert menu.run(**options)['status']=='OFFLINE_PREFLIGHT_PASS' and not options['work'].exists()
    for update in [{'evidence_menu':False},{'numbers':[9,20]},{'committed_results':options['committed_results'][:-1]}]:
        with pytest.raises(ValueError):menu.run(**{**options,**update})
    assert not options['work'].exists()


def test_terminal_race_is_rechecked_under_lock(options,monkeypatch):
    """A stop marker created after preflight blocks even cached provider construction."""
    original=menu.r._exclusive
    @contextmanager
    def raced(path):
        """Introduce a terminal owner signal while acquiring the execution lock."""
        with original(path):menu.r.save(path/'terminal-stop.json',{'status':'STOPPED'});yield
    monkeypatch.setattr(menu.r,'_exclusive',raced);fake=MenuRegistry()
    with pytest.raises(menu.r.SourceFirstStopped):menu.run(**options,registry=fake)
    assert fake.calls==[] and not (options['work']/'execution-receipts').exists()


@pytest.mark.parametrize('reported',[False,True])
def test_v2_unknown_metadata_stays_blocking_raw_untouched_and_resume_free(options,reported):
    """An omitted diagnostic key is unknown metadata, never a guessed grade or PASS."""
    options['review_policy']=menu.BLIND;fake=BlindRegistry(reported=reported)
    result=menu.run(**options,registry=fake)
    assert len(fake.calls)==4 and [r['status'] for r in result['candidates']]==['HOLD_PEER_REVIEW','ACCEPTED_FOR_CASE_ASSIGNMENT']
    stage=menu.r.load(options['work']/'peer_review-shandilya.json')
    native=stage['native']['reviews'][0]['issues'][0];canonical=stage['canonical']['reviews'][0]['issues'][0]
    selected=stage['evidence_mapping']['selections'][0]
    assert ('severity' in native) is reported and selected['native_severity_key_present'] is reported
    assert canonical['severity']==('medium' if reported else menu.UNREPORTED)
    assert selected['severity_origin']==('MODEL_REPORTED' if reported else 'SERVER_MISSINGNESS')
    assert selected['issue_remains_blocking'] is True and selected['native_issue_keys']==sorted(native)
    assert canonical['reason']==native['reason'] and stage['canonical']['reviews'][0]['verdict']=='REVIEW_REQUIRED'
    assert 'model_opinions_unchanged' not in stage['evidence_mapping']
    assert menu.r.load(options['work']/'candidate-002.json')['case_curation_eligible'] is False
    bundle=menu.r.load(options['work']/result['discussion']['path']);supplied=menu.r.load(options['work']/result['input']['path'])
    with pytest.raises(ValueError,match='all three peer reviews PASS'):
        _selection(2,next(b for b in supplied['briefs'] if b['number']==2),supplied['source_packets']['2'],
            bundle['discussion'],bundle['proposal'],bundle['peer_review'])
    manifest=menu.r.load(options['work']/'run-manifest.json');assert manifest['version']==menu.V2_POLICY['version']
    assert menu.run(**options,registry=fake,resume=True)['new_calls']==0 and len(fake.calls)==4
    assert set(fake.peer_views)==set(menu.r.VOICES[:-1])


def test_v2_all_rows_blocking_still_has_three_actual_peers_no_optional_stop(options):
    """Early-stop is deliberately deferred: complete four-call coverage is honest."""
    fake=BlindRegistry(missing=(2,3));result=menu.run(**{**options,'review_policy':menu.BLIND},registry=fake)
    assert len(fake.calls)==4 and all(c['status']=='HOLD_PEER_REVIEW' for c in result['candidates'])
    assert set(fake.peer_views)==set(menu.r.VOICES[:-1])


def v2_request_fixture():
    """Return a pure two-row current review request; no runtime or source certification."""
    request={'scope':'batch','entry_numbers':[2,3],'speaker':'shandilya','review_policy':menu.BLIND,
        'proposal':{'proposals':[{'number':n,'decision':'REJECT','rejection_reason':'Existing synthetic complete source reason only'} for n in (2,3)]}}
    native={'reviews':[{'number':n,'verdict':'REVIEW_REQUIRED','issues':[{'evidence_id':f'P{n:03d}.rejection_reason','reason':'Synthetic remaining source concern'}]} for n in (2,3)]}
    return request,native


@pytest.mark.parametrize('fault',['null','blank','whitespace','numeric','reserved','padded_reserved','extra','foreign','pass_issue','rqr_empty','empty_reason'])
def test_v2_missingness_is_absent_only_not_injection_or_verdict_repair(fault):
    """Malformed explicit values, evidence choices and votes still fail closed."""
    request,native=v2_request_fixture();issue=native['reviews'][0]['issues'][0]
    values={'null':None,'blank':'','whitespace':'  ','numeric':1,'reserved':menu.UNREPORTED,'padded_reserved':' '+menu.UNREPORTED+' '}
    if fault in values:issue['severity']=values[fault]
    elif fault=='extra':issue['quote']='invented'
    elif fault=='foreign':issue['evidence_id']='P003.rejection_reason'
    elif fault=='pass_issue':native['reviews'][0]['verdict']='PASS'
    elif fault=='rqr_empty':native['reviews'][0]['issues']=[]
    else:issue['reason']=''
    catalog=menu.catalog(request);binding={k:catalog[k] for k in ('request_sha256','proposal_sha256','menu_sha256')}
    with pytest.raises(ValueError):menu.materialize(native,request,binding)


def test_strict_v1_still_rejects_exact_same_omission():
    """The new tolerance cannot reinterpret any strict policy's native output."""
    request,native=v2_request_fixture();request.pop('review_policy')
    catalog=menu.catalog(request);binding={k:catalog[k] for k in ('request_sha256','proposal_sha256','menu_sha256')}
    with pytest.raises(ValueError,match='without generated field/quote'):menu.materialize(native,request,binding)


def test_v2_peer_allowlist_has_no_old_opinion_leak_and_keeps_qualified_sources(options):
    """Only the writer sees issue reconciliation; peers see current evidence/counts."""
    fake=BlindRegistry();menu.run(**{**options,'review_policy':menu.BLIND},registry=fake)
    writer=fake.writer_view;peer=fake.peer_views['narada']
    assert writer['original_peer_issues'] and writer['original_proposals'] and writer['discussion']
    for n,packet in peer['sources'].items():
        assert packet['references']==writer['sources'][n]['references']
        assert packet['source_contexts']==writer['sources'][n]['source_contexts']
    # Unique server-only opinions must stay out even if arbitrary extra keys arrive.
    document=menu.r.load(options['work']/'request-peer_review-narada.json')
    assert 'original_peer_issues' not in document['payload']['input']
    assert 'Assess all old issue responses' not in document['payload']['instruction']
    assert 'Address every listed old issue' not in document['system']
    assert all(s['grammar_certified'] is False for s in peer['current_formula_shapes'].values())
    keys=('source_dir','numbers','candidate_sha256','input_sha256','discussion_sha256','offline_gate','batch_gate',
        'menu_gate','committed_results','evidence_menu')
    data=menu.preflight(**{k:options[k] for k in keys},review_policy=menu.BLIND)
    packets={str(c['number']):c['packet'] for c in data['contexts']}
    request={'number':0,'scope':'batch','batch_id':'synthetic-blind-probe','stage':'peer_review','speaker':'narada',
        'entry_numbers':[2,3],'sources':packets,'sources_by_entry':packets,'menu_policy':data['menu_policy'],
        'review_policy':menu.BLIND,'proposal':peer['proposal'],'current_formula_shapes':peer['current_formula_shapes']}
    for key in ('discussion','original_proposals','original_peer_reviews','original_peer_issues','revision_responses','briefs','unknown_future_field'):
        request[key]={'hidden':['UNIQUE_STALE_CRITICISM_MUST_NOT_LEAK']}
    rendered=menu.render('narada',request)
    assert 'UNIQUE_STALE_CRITICISM_MUST_NOT_LEAK' not in json.dumps(rendered)


@pytest.mark.parametrize('damage',['canonical','origin','presence','native'])
def test_v2_cache_rebuild_requires_native_missingness_and_policy_proof(options,damage):
    """Unknownness cannot be cleared, regraded or forged on a cached success."""
    options['review_policy']=menu.BLIND;fake=BlindRegistry();menu.run(**options,registry=fake)
    path=options['work']/'peer_review-shandilya.json';record=menu.r.load(path)
    if damage=='canonical':record['canonical']['reviews'][0]['issues'][0]['severity']='low'
    elif damage=='origin':record['evidence_mapping']['selections'][0]['severity_origin']='MODEL_REPORTED'
    elif damage=='presence':record['evidence_mapping']['selections'][0]['native_severity_key_present']=True
    else:record['native']['reviews'][0]['issues'][0]['severity']='low'
    menu.r.save(path,record);before=len(fake.calls)
    with pytest.raises(menu.r.SourceFirstStopped):menu.run(**options,registry=fake,resume=True)
    assert len(fake.calls)==before


def test_v2_cannot_switch_or_reinterpret_existing_v1_root(options):
    """Existing manifest/version/policy binding rejects reinterpretation before dispatch."""
    fake=MenuRegistry();menu.run(**options,registry=fake);before=len(fake.calls);saved=snapshot(options['work'])
    with pytest.raises(ValueError,match='binding/cap drift'):
        menu.run(**{**options,'review_policy':menu.BLIND},registry=fake,resume=True)
    assert len(fake.calls)==before and snapshot(options['work'])==saved


def test_v2_explicitly_excludes_closed_87_88_scope(options):
    """Closed calibration cannot be repaid by selecting the new policy on a new root."""
    with pytest.raises(ValueError):menu.run(**{**options,'numbers':[87,88],'review_policy':menu.BLIND})
    assert not options['work'].exists()

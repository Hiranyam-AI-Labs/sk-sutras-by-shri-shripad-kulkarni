"""Synthetic SDK/SQLite checks for exact approved row81 evidence localization only."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest
from scripts import run_source_first_selection as selection
from scripts import adopt_source_first_evidence_anchor as operator
from src.orchestration import source_first_evidence_anchor as anchor
from src.orchestration.research_council import ResearchCouncil, VOICES, SOURCE_FIRST_SELECTION, _json
from src.orchestration.source_first_provider import SourceFirstProvider
from tests.test_source_first_selection_runner import research, SelectionRegistry

REASON81 = "अन्याश्रयत्याग हा अंतिम आध्यात्मिक आधाराबद्दल आहे, व्यवहारातील सहकार्य नाकारण्याबद्दल नाही. गीता ९.२२ अटींसह आणि आध्यात्मिक आश्वासन देते. एक मूलनिष्ठा हा व्यावसायिक अर्थ 'एकं लक्ष्यं विक्षेपेषूदासीनता' शी जुळतो आणि held entries शीही."
BADQUOTE = "'एकं लक्ष्यं विक्षेपेषूदासीनता' शी जुळते आणि held entries शीही."


class AnchorRegistry(SelectionRegistry):
    """Produce two complete synthetic quote-invalid researcher SDK responses."""
    def respond(self, voice, payload):
        """Use normal four-voice fixtures; only researcher81 citation is invalid."""
        answer=super().respond(voice,payload)
        if payload['stage']=='proposal':
            answer['proposals']=[p if p['number']==80 else {'number':p['number'],'decision':'REJECT',
                'rejection_reason':REASON81 if p['number']==81 else 'हा नकार या विशिष्ट चाचणीतील स्पष्ट कारणासाठी दिला आहे.'} for p in answer['proposals']]
        if payload['stage']=='peer_review' and voice=='researcher':
            self.researcher_count=getattr(self,'researcher_count',0)+1
            proposals={p['number']:p for p in payload['proposal']['proposals']}
            for row in answer['reviews']:
                n=row['number'];bad=n in [74,75,77,78,79,81] or (n==72 and self.researcher_count==1)
                row.update(verdict='REVIEW_REQUIRED' if bad else 'PASS',issues=[])
                if bad:row['issues']=[{'field':'rejection_reason','quote':BADQUOTE if n==81 else proposals[n]['rejection_reason'],
                    'reason':'चाचणीतील हा स्पष्ट आक्षेप आणि त्याचे कारण जतन करावे.','severity':'medium'}]
        return answer


@pytest.fixture(autouse=True)
def no_live_factories(monkeypatch):
    """Trip on live registry/credentials construction even during negative tests."""
    def blocked(*args,**kwargs):
        """Any unplanned live factory access is a hard test failure, never a call."""
        pytest.fail('No live factories or credentials in anchor tests')
    monkeypatch.setattr('src.orchestration.source_first_provider.create_live_provider',blocked)
    monkeypatch.setattr('scripts.run_research_book.load_project_credentials',blocked)
    monkeypatch.setattr('src.providers.registry.ProviderRegistry',blocked)


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    """Create fifteen real fake-boundary caches plus two FAILED reviews and approval.

    Every artifact lives in short TEMP. No production source/readiness labels are
    imported; the approval and execution gate are explicitly synthetic fixtures.
    """
    plan,screening,refs=research(10);entries=selection.build_selection(plan,screening,refs)['entries']
    for n,e in zip(anchor.NUMBERS,entries):e['number']=n;e['brief']['number']=n
    briefs=[e['brief'] for e in entries];briefs[0]['selection_history']=[]
    packets={str(e['number']):e['source_packet'] for e in entries};name='selection-'+'-'.join(map(str,anchor.NUMBERS))
    source=tmp_path/'original';source.mkdir();binding={'fixture':'a'*64}
    selection.save(source/'run-manifest.json',{'binding':binding,'live':False,'budget':20.,'claude_cap':15.,'max_calls':100})
    forbidden=['चाचणीपुरती मूळ सूत्रनोंद']
    selection.save(source/'selection-1-discussion.json',{'discussion':{'_batch':{'forbidden_originals':forbidden}}})
    ip=source/(name+'-input.json');selection.save(ip,{'briefs':briefs,'source_packets':packets,'prior_formulas':[]})
    registry=AnchorRegistry();provider=SourceFirstProvider(source/'provider',registry,source_hashes=binding,max_usd=20.,claude_cap_usd=15.,max_calls=100)
    calls=selection.SelectionCalls(provider,source);dbpath=source/('council.db.batch-'+hashlib.sha256(_json(name).encode()).hexdigest()+'.sqlite3')
    def forbidden_callback(*args,**kwargs):
        """Trip on any unexpected composition, validation or replay SDK callback."""
        pytest.fail('No extra SDK/composition/validator calls')
    council=ResearchCouncil(dbpath,{v:(lambda p,v=v:calls.voice(v,p)) for v in VOICES},forbidden_callback,forbidden_callback,source_first_selection=True)
    base={'number':0,'brief':{'batch_id':name},'sources':packets,'scope':'batch','batch_id':name,'briefs':briefs,
        'entry_numbers':anchor.NUMBERS,'sources_by_entry':packets,'prior_formulas':[],'forbidden_originals':forbidden,'used_case_ids':[],'source_first_selection':SOURCE_FIRST_SELECTION}
    council._bind(0,base);discussion={}
    for stage in ('position','challenge','reply'):
        discussion[stage]={v:council._stage({**base,'discussion':deepcopy(discussion),'stage':stage,'speaker':v},council.voices[v]) for v in VOICES}
    proposal=council._stage({**base,'discussion':discussion,'stage':'proposal','speaker':'sutrakar'},council.voices['sutrakar'])
    for voice in ('narada','shandilya'):
        council._stage({**base,'discussion':discussion,'proposal':proposal,'stage':'peer_review','speaker':voice},council.voices[voice])
    request={**base,'discussion':discussion,'proposal':proposal,'stage':'peer_review','speaker':'researcher'}
    with pytest.raises(ValueError,match='Exhausted'):council._stage(request,council.voices['researcher'])
    with anchor._ro(dbpath) as db:
        db.row_factory=sqlite3.Row
        attempts=[dict(r) for r in db.execute("SELECT * FROM research_attempts WHERE stage='peer_review' AND speaker='researcher' ORDER BY attempt")]
        stages=[dict(r) for r in db.execute('SELECT * FROM research_stages')]
    slot=anchor.digest(['researcher',f'batch/{name}/peer_review/schema-correction'])
    with anchor._ro(provider.db_path) as db:
        db.row_factory=sqlite3.Row;row=dict(db.execute('SELECT * FROM calls WHERE slot=?',(slot,)).fetchone())
    original=json.loads(attempts[-1]['response_json']);patched=deepcopy(original);patched['reviews'][9]['issues'][0]['quote']=anchor.SPAN
    def ref(path):
        """Bind fixture artifact bytes at their absolute location."""
        return {'path':str(Path(path).resolve()),'sha256':selection.byte_hash(path)}
    siblings=[{'stage':r['stage'],'speaker':r['speaker'],'request_sha256':r['request_hash'],'response_json_sha256':hashlib.sha256(r['response_json'].encode()).hexdigest()} for r in stages]
    field=REASON81;quote=BADQUOTE
    design={'schema':'source-first-exact-existing-evidence-span-adoption-design-v1',
        'target':{'batch':name,'council_db':str(dbpath.resolve()),'number':0,'stage':'peer_review','speaker':'researcher','latest_attempt':2,'entry_number':81,'issue_index':0,'json_pointer':'/reviews/9/issues/0/quote'},
        'original_bindings':{'input':ref(ip),'run_manifest':ref(source/'run-manifest.json'),'immutable_business_binding':binding,'source_sha256':row['source_sha256'],
            'all15_cached_stage_bindings':siblings,'core_request_sha256':attempts[-1]['request_hash'],'proposal_parsed_sha256':anchor.digest(proposal),'latest_response_parsed_sha256':anchor.digest(original),
            'latest_original_failed_attempt':{'attempt':2,'state':'FAILED','error':anchor.ERROR,'response_json_sha256':hashlib.sha256(attempts[-1]['response_json'].encode()).hexdigest()},
            'paid_slot':slot,'actual_paid_request_sha256':row['request_sha256'],'raw_latest_response':ref(provider.work_dir/'raw'/(slot+'.txt'))},
        'explicit_anchor_witness':{'current_proposal_81_exact':next(p for p in proposal['proposals'] if p['number']==81),'current_field_exact':field,'invalid_original_issue_exact':original['reviews'][9]['issues'][0],
            'original_quote_exact':quote,'selected_existing_span_exact':anchor.SPAN,'original_quote_start_codepoint':quote.index(anchor.SPAN),'original_quote_end_codepoint':quote.index(anchor.SPAN)+len(anchor.SPAN),
            'current_field_start_codepoint':field.index(anchor.SPAN),'current_field_end_codepoint':field.index(anchor.SPAN)+len(anchor.SPAN),'new_or_replaced_characters':0,'normalization_performed':False,'morphological_rewrite':False,
            'original_quote_utf8_sha256':hashlib.sha256(quote.encode()).hexdigest(),'selected_span_utf8_sha256':hashlib.sha256(anchor.SPAN.encode()).hexdigest(),'current_field_utf8_sha256':hashlib.sha256(field.encode()).hexdigest(),
            'original_quote_selected_utf8_hex':anchor.SPAN.encode().hex(),'current_field_selected_utf8_hex':anchor.SPAN.encode().hex()},
        'preview_only_validation':{'proposed_locally_anchored_answer_sha256':anchor.digest(patched)}}
    dp=tmp_path/'design.json';selection.save(dp,design)
    approved={'core_request_sha256':attempts[-1]['request_hash'],'paid_request_sha256':row['request_sha256'],'paid_slot':slot,'source_sha256':row['source_sha256'],'raw_sha256':row['raw_sha256'],'original_review_answer_sha256':anchor.digest(original),
        'target_proposal_sha256':anchor.digest(proposal),'target_full_field_sha256':hashlib.sha256(field.encode()).hexdigest(),'derived_copy_sha256':anchor.digest(patched)}
    exact={'selected_shared_span':anchor.SPAN,'original_full_quote':quote,'original_reason_unchanged':original['reviews'][9]['issues'][0]['reason'],'severity_unchanged':'medium','verdict_unchanged':'REVIEW_REQUIRED',
        'span_utf8_sha256':hashlib.sha256(anchor.SPAN.encode()).hexdigest(),'start_in_original_quote_codepoints':quote.index(anchor.SPAN),'end_in_original_quote_codepoints':quote.index(anchor.SPAN)+len(anchor.SPAN),
        'start_in_target_field_codepoints':field.index(anchor.SPAN),'end_in_target_field_codepoints':field.index(anchor.SPAN)+len(anchor.SPAN)}
    approval={'status':'PASS_SHARED_EXISTING_SPAN_DESIGN_ONLY','gate':'PASS_DESIGN_ONLY','required_issues':[],'reviewed_saved_design':ref(dp),'bindings':approved,'exact_selection':exact,'verification':{'all_votes_reasons_severities_fields_otherquotes_identical':True}}
    ap=tmp_path/'approval.json';selection.save(ap,approval)
    kwargs={'design':str(dp),'design_sha256':selection.byte_hash(dp),'approval':str(ap),'approval_sha256':selection.byte_hash(ap),'output':str(tmp_path/'operator'/'receipt.json')}
    result=operator.prepare(**kwargs);rp=Path(result['path'])
    monkeypatch.setattr(operator,'code_bindings',lambda:{'synthetic-current':'f'*64})
    gate=tmp_path/'gate.json';selection.save(gate,{'status':'PASS','paid_calls':0,'code_sha256':operator.code_bindings(),'tests':[{'path':p,'passed':1,'failed':0,'errors':0} for p in operator.REQUIRED_TESTS]})
    monkeypatch.setattr(anchor,'FAILED_CORE',attempts[-1]['request_hash'])
    return {'source':source,'provider':provider,'registry':registry,'council':council,'base':base,'request':request,'db':dbpath,'attempts':attempts,'stages':stages,
        'original':original,'patched':patched,'receipt':rp,'sha':result['sha256'],'gate':gate,'design':dp,'approval':ap,'prepare_kwargs':kwargs,'tripwire':forbidden_callback}


def apply(data):
    """Invoke actual offline operator with an external synthetic exact-code gate."""
    return operator.apply(receipt=data['receipt'],receipt_sha256=data['sha'],offline_gate=data['gate'])


def test_apply_and_full_sixteen_stage_cached_replay_is_lossless_and_zero_sdk(prepared):
    """All cached rounds replay; only one quote narrows while old failures/raw remain."""
    d=prepared;provider_files=[d['provider'].db_path,d['provider'].work_dir/'dispatch.db',*list((d['provider'].work_dir/'raw').glob('*.txt'))]
    fingerprints={str(p):anchor.byte_hash(p) for p in provider_files};before=len(d['registry'].calls)
    assert apply(d)['status']=='EVIDENCE_SPAN_ADOPTED'
    result=d['council']._deliberate(d['base'])
    latest=result['peer_review']['researcher'];marker=latest.pop(anchor.MARKER)
    assert latest==d['patched'] and latest['reviews'][0]['verdict']=='PASS'
    assert [r['number'] for r in latest['reviews'] if r['verdict']=='REVIEW_REQUIRED']==[74,75,77,78,79,81]
    assert latest['reviews'][9]['issues'][0]['quote']==anchor.SPAN
    assert len(d['registry'].calls)==before and all(anchor.byte_hash(p)==sha for p,sha in fingerprints.items())
    with anchor._ro(d['db']) as db:
        db.row_factory=sqlite3.Row
        assert [dict(r) for r in db.execute("SELECT * FROM research_attempts WHERE stage='peer_review' AND speaker='researcher' ORDER BY attempt")]==d['attempts']
        assert db.execute('SELECT count(*) FROM research_stages').fetchone()[0]==16
    assert apply(d)['status']=='EVIDENCE_SPAN_ADOPTED' and len(d['registry'].calls)==before


@pytest.mark.parametrize('damage',['verdict','reason','other_quote','span','receipt_kind','raw','proposal','attempt','request','approval'])
def test_drift_cannot_adopt_or_invent_pass(prepared,damage):
    """Changing any proof or other semantic field blocks before insertion/callback."""
    d=prepared;receipt=selection.load(d['receipt'])
    if damage in ('verdict','reason','other_quote','span','receipt_kind'):
        if damage=='verdict':receipt['anchored_answer']['reviews'][0]['verdict']='REVIEW_REQUIRED'
        elif damage=='reason':receipt['anchored_answer']['reviews'][2]['issues'][0]['reason']='changed'
        elif damage=='other_quote':receipt['anchored_answer']['reviews'][2]['issues'][0]['quote']='changed'
        elif damage=='span':receipt['anchored_answer']['reviews'][9]['issues'][0]['quote']='एकं लक्ष्यं'
        else:receipt['kind']='PARTIAL_STAGE_COMPLETION'
        selection.save(d['receipt'],receipt);d['sha']=selection.byte_hash(d['receipt'])
    elif damage=='raw':
        row=receipt['original_provider_calls'][1];(d['provider'].work_dir/'raw'/(row['slot']+'.txt')).write_text('{}',encoding='utf-8')
    elif damage=='approval':
        approval=selection.load(d['approval']);approval['gate']='PENDING';selection.save(d['approval'],approval)
    else:
        with sqlite3.connect(d['db']) as db:
            if damage=='proposal':db.execute("UPDATE research_stages SET response_json='{}' WHERE stage='proposal'")
            elif damage=='attempt':db.execute("UPDATE research_attempts SET state='COMPLETE' WHERE stage='peer_review' AND speaker='researcher' AND attempt=2")
            else:db.execute("UPDATE research_attempts SET request_hash='wrong' WHERE stage='peer_review' AND speaker='researcher' AND attempt=2")
    before=len(d['registry'].calls)
    with pytest.raises((ValueError,KeyError)):apply(d)
    with anchor._ro(d['db']) as db:assert db.execute("SELECT count(*) FROM research_stages WHERE stage='peer_review' AND speaker='researcher'").fetchone()[0]==0
    assert len(d['registry'].calls)==before


@pytest.mark.parametrize('damage',['marker','table','authority','everything','receipt','stage_result','foreign_db'])
def test_mandatory_receipt_replay_cannot_be_stripped(prepared,damage,tmp_path):
    """Every adopted cache revalidates authority/history/raw, including stripped tags."""
    d=prepared;apply(d)
    with sqlite3.connect(d['db']) as db:
        if damage in ('marker','everything','stage_result'):
            saved=json.loads(db.execute("SELECT response_json FROM research_stages WHERE stage='peer_review' AND speaker='researcher'").fetchone()[0])
            if damage=='stage_result':saved['reviews'][0]['verdict']='REVIEW_REQUIRED'
            else:saved.pop(anchor.MARKER)
            db.execute("UPDATE research_stages SET response_json=? WHERE stage='peer_review' AND speaker='researcher'",(_json(saved),))
        if damage in ('table','everything'):db.execute('DROP TABLE evidence_span_authorities')
        if damage=='authority':db.execute('DELETE FROM evidence_span_authorities')
        if damage=='everything':db.execute("DELETE FROM research_attempts WHERE stage='peer_review' AND speaker='researcher'")
    if damage=='receipt':d['receipt'].unlink()
    if damage=='foreign_db':
        other=tmp_path/'foreign.sqlite3'
        with anchor._ro(d['db']) as old,sqlite3.connect(other) as new:old.backup(new)
        d['council'].path=other
    before=len(d['registry'].calls)
    with pytest.raises((ValueError,FileNotFoundError)):d['council']._stage(d['request'],d['tripwire'])
    assert len(d['registry'].calls)==before


def test_gate_is_current_and_rechecked_under_lock(prepared,monkeypatch):
    """A gate becoming stale after preflight cannot write an authority or stage."""
    d=prepared
    @contextmanager
    def race(path):
        """Change only synthetic gate at lock acquisition, never original artifacts."""
        gate=selection.load(d['gate']);gate['code_sha256']={};selection.save(d['gate'],gate)
        yield
    monkeypatch.setattr(operator,'_exclusive',race)
    with pytest.raises(ValueError,match='gate'):apply(d)
    with anchor._ro(d['db']) as db:assert db.execute('SELECT count(*) FROM research_stages').fetchone()[0]==15
    assert not (d['receipt'].parent/'execution-receipts').exists()


def test_explicit_prepare_never_overwrites_or_writes_originals(prepared):
    """Only a fresh external receipt output is allowed; preparation never adopts."""
    d=prepared
    with pytest.raises(ValueError,match='Fresh'):operator.prepare(**d['prepare_kwargs'])
    opts={**d['prepare_kwargs'],'output':str(d['source']/'forbidden.json')}
    with pytest.raises(ValueError,match='outside'):operator.prepare(**opts)
    assert not (d['source']/'forbidden.json').exists()
    with anchor._ro(d['db']) as db:assert db.execute('SELECT count(*) FROM research_stages').fetchone()[0]==15



@pytest.mark.parametrize('damage',['offset','short_span','morphology','wrong_target','older_attempt','approval_offset','approval_request','approval_issues'])
def test_even_approved_fixture_cannot_expand_exact_span_scope(prepared,damage,tmp_path):
    """A synthetic reapproval never enables a different target, new text or bad witness."""
    d=prepared;design=selection.load(d['design']);approval=selection.load(d['approval'])
    if damage=='offset':design['explicit_anchor_witness']['original_quote_start_codepoint']+=1
    elif damage=='short_span':design['explicit_anchor_witness']['selected_existing_span_exact']='एकं लक्ष्यं'
    elif damage=='morphology':design['explicit_anchor_witness']['morphological_rewrite']=True
    elif damage=='wrong_target':design['target']['entry_number']=80
    elif damage=='older_attempt':design['target']['latest_attempt']=1
    elif damage=='approval_offset':approval['exact_selection']['start_in_target_field_codepoints']+=1
    elif damage=='approval_request':approval['bindings']['paid_request_sha256']='f'*64
    else:approval['required_issues']=['Not approved']
    selection.save(d['design'],design);approval['reviewed_saved_design']['sha256']=selection.byte_hash(d['design']);selection.save(d['approval'],approval)
    opts={**d['prepare_kwargs'],'design_sha256':selection.byte_hash(d['design']),'approval_sha256':selection.byte_hash(d['approval']),'output':str(tmp_path/'new-receipt.json')}
    with pytest.raises(ValueError):operator.prepare(**opts)
    assert not Path(opts['output']).exists()


def test_competing_stage_at_lock_is_not_overwritten(prepared,monkeypatch):
    """A locally raced cache cannot be treated as the authorized missing stage."""
    d=prepared
    @contextmanager
    def race(path):
        """Insert an unrelated fixture cache after outer checks, before locked checks."""
        with sqlite3.connect(d['db']) as db:
            db.execute('INSERT INTO research_stages VALUES (?,?,?,?,?)',(*anchor.KEY,d['attempts'][1]['request_hash'],_json(d['patched'])))
        yield
    monkeypatch.setattr(operator,'_exclusive',race)
    with pytest.raises(ValueError,match='authority'):apply(d)
    with anchor._ro(d['db']) as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='evidence_span_authorities'").fetchone()
        assert json.loads(db.execute("SELECT response_json FROM research_stages WHERE stage='peer_review' AND speaker='researcher'").fetchone()[0])==d['patched']

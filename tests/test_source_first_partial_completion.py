"""Offline real-boundary/council partial-stage recovery; synthetic SDKs only."""
from copy import deepcopy
import hashlib,json,sqlite3
from pathlib import Path
import pytest
from scripts import run_source_first_selection as s
from src.orchestration import source_first_partial_completion as partial
from src.orchestration.source_first_provider import SourceFirstProvider,SourceFirstStopped,_hash
from src.orchestration.research_council import ResearchCouncil,VOICES,SOURCE_FIRST_SELECTION,_json
from tests.test_source_first_selection_runner import research,SelectionRegistry
from tests.test_source_first_provider import FakeAdapter,FakeRegistry


class PartialRegistry(SelectionRegistry):
    """Return eight complete reviews and one actual truncated fake SDK response."""
    def generate(self,voice,adapter,prompt,system):
        """Preserve ordinary stages; mark only the selected final peer incomplete."""
        response=super().generate(voice,adapter,prompt,system)
        payload=json.loads(prompt)['input']
        if voice=='narada' and payload['stage']=='peer_review':
            rows=json.loads(response.content)['reviews'][:8]
            rows[5].update(verdict='REVIEW_REQUIRED',issues=[{'field':'proposed_sutra',
                'quote':'उद्यमेन विवेकः','reason':'Synthetic critical objection retained exactly','severity':'CRITICAL'}])
            response.content='```json\n{"reviews":['+','.join(json.dumps(r,ensure_ascii=False) for r in rows)+',{"number":30,"verdict'
            response.was_truncated=True;response.finish_reason='MAX_TOKENS'
        return response


class CompletionRegistry(SelectionRegistry):
    """One Narada SDK response with retained visible/thought usage counters."""
    def generate(self,voice,adapter,prompt,system):
        """Return two model judgments, not inferred/padded missing records."""
        assert voice=='narada'
        response=super().generate(voice,adapter,prompt,system)
        response.usage.output_tokens=30;response.usage.total_tokens=40
        response.usage.raw_usage={'prompt_token_count':10,'candidates_token_count':10,
            'thoughts_token_count':20,'total_token_count':40}
        return response


def setup_original(tmp_path):
    """Make actual fifteen cached council stages plus a truncated sixteenth."""
    plan,screening,refs=research(10);prepared=s.build_selection(plan,screening,refs)
    entries=prepared['entries'];numbers=list(range(22,32))
    for n,e in zip(numbers,entries):e['number']=n;e['brief']['number']=n
    briefs=[e['brief'] for e in entries];briefs[0]['selection_history']=[]
    packets={str(e['number']):e['source_packet'] for e in entries}
    batch='selection-'+'-'.join(map(str,numbers));work=tmp_path/'old';work.mkdir()
    source_input=work/(batch+'-input.json')
    s.save(source_input,{'briefs':briefs,'source_packets':packets,'prior_formulas':[],'prior_accepted_decisions':[]})
    provider=SourceFirstProvider(work/'provider',PartialRegistry(),source_hashes={'source':'a'*64},max_usd=20.,claude_cap_usd=15.,max_calls=100)
    calls=s.SelectionCalls(provider,work)
    path=work/('council.db.batch-'+hashlib.sha256(_json(batch).encode()).hexdigest()+'.sqlite3')
    fail=lambda *args:pytest.fail('No composition/validator')
    council=ResearchCouncil(path,{v:(lambda p,v=v:calls.voice(v,p)) for v in VOICES},fail,fail,source_first_selection=True)
    forbidden=['चाचणी सूत्र वर्ज्य']
    base={'number':0,'brief':{'batch_id':batch},'sources':packets,'scope':'batch','batch_id':batch,'briefs':briefs,
          'entry_numbers':numbers,'sources_by_entry':packets,'prior_formulas':[],'forbidden_originals':forbidden,
          'used_case_ids':[],'source_first_selection':SOURCE_FIRST_SELECTION}
    council._bind(0,base);discussion={}
    for stage in ('position','challenge','reply'):
        discussion[stage]={v:council._stage({**base,'discussion':deepcopy(discussion),'stage':stage,'speaker':v},council.voices[v]) for v in VOICES}
    proposal=council._stage({**base,'discussion':discussion,'stage':'proposal','speaker':'sutrakar'},council.voices['sutrakar'])
    for v in ('shandilya','researcher'):
        council._stage({**base,'discussion':discussion,'proposal':proposal,'stage':'peer_review','speaker':v},council.voices[v])
    request={**base,'discussion':discussion,'proposal':proposal,'stage':'peer_review','speaker':'narada'}
    with pytest.raises(SourceFirstStopped):council._stage(request,council.voices['narada'])
    slot=_hash(['narada',f'batch/{batch}/peer_review'])
    row=partial._call_row(provider.work_dir,slot)
    saved=partial.prepare_plan(provider.work_dir,path,source_input,forbidden,slot,
        expected_request_sha256=row['request_sha256'],expected_raw_sha256=row['raw_sha256'],expected_source_sha256=row['source_sha256'])
    return saved,provider,council,request


def complete(tmp_path,plan):
    """Use one real durable fake-boundary completion call and produce its receipt."""
    registry=CompletionRegistry()
    provider=SourceFirstProvider(tmp_path/'completion',registry,source_hashes={'partial_plan':partial.digest(plan)},max_usd=.25,claude_cap_usd=.001,max_calls=1)
    call=partial.completion_call(plan)
    answer=provider(**call)
    receipt=partial.finalize_receipt(plan,provider.work_dir)
    path=tmp_path/'completion-receipt.json';s.save(path,receipt)
    return path,provider,registry,answer


@pytest.fixture
def original(tmp_path):
    """Return isolated synthetic old-stage failure; no production files or keys."""
    return setup_original(tmp_path)


def test_prefix_missing_only_projection_critical_retention_and_no_early_adoption(original):
    """Eight real rows survive; partial30 is discarded, not guessed or approved."""
    plan,provider,council,request=original
    assert [r['number'] for r in plan['prefix']['rows']]==list(range(22,30))
    assert plan['missing_numbers']==[30,31]
    assert plan['prefix']['rows'][5]['issues'][0]['severity']=='CRITICAL'
    assert partial.project_completion_request(plan)['entry_numbers']==[30,31]
    assert len(plan['cached_siblings'])==15
    assert partial._call_row(provider.work_dir,plan['failed_slot'])['status']=='HARD_FAILED'


def test_complete_apply_replay_and_next_call_clearance_without_rebilling(original,tmp_path):
    """Only composite logical caches change; original dispatch/raw/attempt remain."""
    plan,provider,council,request=original
    oldraw=(provider.work_dir/'raw'/(plan['failed_slot']+'.txt')).read_bytes()
    path,child,registry,answer=complete(tmp_path,plan)
    assert len(registry.calls)==1 and child.dispatcher.calls==1
    result=partial.apply_receipt(path)
    assert result['status']=='COMPOSITE_RECOVERED'
    with sqlite3.connect(plan['council_db']) as db:
        assert db.execute("SELECT state FROM research_attempts WHERE stage='peer_review' AND speaker='narada'").fetchone()[0]=='HARD_FAILED'
    resumed=council._stage(request,lambda _:pytest.fail('No repeated peer or discussion call'))
    assert resumed['reviews'][:8]==plan['prefix']['rows']
    assert [r['number'] for r in resumed['reviews']]==list(range(22,32))
    oldcall=plan['original_model_call']
    before=provider.dispatcher.calls
    cached=provider(**oldcall)
    assert cached==resumed and provider.dispatcher.calls==before
    assert (provider.work_dir/'raw'/(plan['failed_slot']+'.txt')).read_bytes()==oldraw
    assert partial._audit(provider.work_dir,plan['original_failed_row']['raw_sha256'],'INCOMPLETE')==plan['original_dispatch']
    partial.verify_authorities(provider.work_dir)
    assert partial.apply_receipt(path)['status']=='COMPOSITE_RECOVERED'


@pytest.mark.parametrize('tamper',['new_result','original_proposal','receipt','raw','sibling'])
def test_tamper_cannot_adopt_or_clear_failure(original,tmp_path,tamper):
    """Consistent JSON cache edits never override real raw judgments or old context."""
    plan,provider,council,request=original
    path,child,registry,answer=complete(tmp_path,plan)
    if tamper=='new_result':
        altered=deepcopy(answer);altered['reviews'][0]['verdict']='REVIEW_REQUIRED';altered['reviews'][0]['issues']=[{'field':'proposed_sutra','quote':'उद्यमेन विवेकः','reason':'Forged','severity':'major'}]
        with sqlite3.connect(child.db_path) as db:db.execute('UPDATE calls SET result_json=?,result_sha256=?',(json.dumps(altered,ensure_ascii=False,sort_keys=True,separators=(',',':')),partial.digest(altered)))
    elif tamper=='original_proposal':
        receipt=s.load(path);receipt['plan']['original_core_request']['proposal']['proposals'][0]['derivation']='Altered';s.save(path,receipt)
    elif tamper=='receipt':
        receipt=s.load(path);receipt['merged']['reviews'][5]={'number':27,'verdict':'PASS','issues':[]};s.save(path,receipt)
    elif tamper=='raw':(child.work_dir/'raw'/(_hash(['narada','missing-peer-review'])+'.txt')).write_bytes(b'changed')
    else:
        with sqlite3.connect(plan['council_db']) as db:db.execute("UPDATE research_stages SET response_json='{}' WHERE stage='peer_review' AND speaker='shandilya'")
    with pytest.raises((ValueError,KeyError)):partial.apply_receipt(path)
    assert partial._call_row(provider.work_dir,plan['failed_slot'])['status']=='HARD_FAILED'


def test_receipt_reverified_before_future_call_or_council_cache(original,tmp_path):
    """An altered composite blocks even other cached/new calls, not just its slot."""
    plan,provider,council,request=original;path,_,_,_=complete(tmp_path,plan);partial.apply_receipt(path)
    receipt=s.load(path);receipt['merged']['reviews'][0]['verdict']='REVIEW_REQUIRED';s.save(path,receipt)
    before=provider.dispatcher.calls
    with pytest.raises(ValueError):provider('narada','future-stage','system',{'test':'new'},100)
    with pytest.raises(ValueError):council._stage(request,lambda _:pytest.fail('No callback'))
    assert provider.dispatcher.calls==before


def test_other_hard_failure_still_blocks_clearance(original,tmp_path):
    """Completion is not a general failure waiver or timeout replacement."""
    plan,provider,_,_=original;path,_,_,_=complete(tmp_path,plan);partial.apply_receipt(path)
    with sqlite3.connect(provider.db_path) as db:
        db.execute("INSERT INTO calls VALUES (?,?,?,'HARD_FAILED',NULL,NULL,NULL,'OTHER_FAILURE')",('f'*64,'b'*64,'c'*64))
    with pytest.raises(SourceFirstStopped):provider('narada','future-stage','system',{'x':1},100)


def test_old_default_and_new_thinking_options_have_distinct_exact_identity(tmp_path):
    """Legacy default cache remains reusable while explicit controls are hashbound."""
    registry=FakeRegistry();provider=SourceFirstProvider(tmp_path/'p',registry,source_hashes={'s':'a'*64},max_usd=1.,claude_cap_usd=.5,max_calls=5)
    payload={'test':'same'};provider('narada','legacy','system',payload,100)
    oldcalls=provider.dispatcher.calls
    tokens,options=provider.future_request_parameters('narada','legacy','system',payload,100,16384,{'thinking_level':'MEDIUM'})
    assert (tokens,options)==(100,None)
    provider('narada','legacy','system',payload,tokens)
    assert provider.dispatcher.calls==oldcalls
    provider('narada','new','system',payload,16384,generation_options={'thinking_level':'MEDIUM'})
    with pytest.raises(ValueError):provider('narada','new','system',payload,16384,generation_options={'thinking_level':'HIGH'})



@pytest.mark.parametrize('damage',['missing_table','deleted_authority','stripped_marker'])
def test_no_composite_can_clear_future_calls_without_authority(original,tmp_path,damage):
    """Removing explicit receipt metadata never converts truncation to ordinary success."""
    plan,provider,_,_=original;path,_,_,_=complete(tmp_path,plan);partial.apply_receipt(path)
    with sqlite3.connect(provider.db_path) as db:
        if damage=='deleted_authority':db.execute('DELETE FROM partial_stage_completions')
        else:db.execute('DROP TABLE partial_stage_completions')
        if damage=='stripped_marker':db.execute("UPDATE calls SET error_type=NULL WHERE slot=?",(plan['failed_slot'],))
    before=provider.dispatcher.calls
    with pytest.raises(ValueError):provider('narada','future','system',{'x':1},100)
    assert provider.dispatcher.calls==before


def test_configured_adapter_empty_override_is_still_bound(tmp_path):
    """An empty caller override cannot hide a configured SDK thinking tier."""
    class ThinkingAdapter(FakeAdapter):
        """Expose actual adapter generation controls for boundary identity tests."""
        @property
        def generation_options(self):
            """Return configured tier, no implicit control when absent."""
            return {'thinking_level':self.thinking_level} if getattr(self,'thinking_level',None) else {}
    registry=FakeRegistry();role=s.MODELS['narada'][0]
    adapter=ThinkingAdapter('narada');adapter.thinking_level='MEDIUM';registry.adapters[role]=adapter
    provider=SourceFirstProvider(tmp_path/'configured',registry,source_hashes={'s':'a'*64},max_usd=1.,claude_cap_usd=.5,max_calls=2)
    provider('narada','configured','s',{'x':1},100,generation_options={})
    with sqlite3.connect(provider.db_path) as db:request=db.execute('SELECT request_sha256 FROM calls').fetchone()[0]
    expected=_hash({'voice':'narada','stage':'configured','system':'s','payload':{'x':1},'max_output_tokens':100,
                    'config':provider.config_hash,'sources':_hash(provider.source_hashes),'generation_options':{'thinking_level':'MEDIUM'}})
    assert request==expected


@pytest.mark.skipif(__import__('os').name!='nt',reason='Actual extended Windows drive path')
def test_extended_windows_readonly_path_and_reserved_characters(tmp_path):
    """Extended drive URI reads exact existing bytes, denies writes and creation."""
    path=tmp_path/'proof #100% मराठी.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE proof(value TEXT)');db.execute("INSERT INTO proof VALUES ('exact')")
    extended='\\\\?\\'+str(path.resolve())
    assert __import__('urllib.parse',fromlist=['urlsplit']).urlsplit(partial._readonly_uri(extended)).netloc==''
    for supplied in (path,extended):
        with partial._ro(supplied) as db:
            assert db.execute('SELECT value FROM proof').fetchall()==[('exact',)]
            with pytest.raises(sqlite3.OperationalError,match='readonly'):
                db.execute("INSERT INTO proof VALUES ('forbidden')")
    missing=tmp_path/'missing #100%.db'
    with pytest.raises(sqlite3.OperationalError):partial._ro('\\\\?\\'+str(missing.resolve()))
    assert not missing.exists()


def test_readonly_unc_and_drive_uri_encoding_without_network():
    """Native UNC/extended paths retain their prefix with no URI host or option injection."""
    from urllib.parse import urlsplit,unquote
    for original in (r'\\?\UNC\server\share\proof #100%.db',r'\\server\share\proof #100%.db',r'\\?\C:\proof ?mode=rw#100%.db'):
        uri=partial._readonly_uri(original);parts=urlsplit(uri)
        assert parts.netloc=='' and parts.query=='mode=ro' and not parts.fragment
        assert unquote(parts.path)==original
    assert partial._readonly_uri(r'C:\proof #100%.db')=='file:///C:/proof%20%23100%25.db?mode=ro'


@pytest.mark.skipif(__import__('os').name!='nt',reason='Actual extended Windows long path')
def test_extended_windows_long_path_remains_readonly(tmp_path):
    """An existing over-260-character proof stays readable without losing its native prefix."""
    path=tmp_path/('a'*85)/('b'*85)/('c'*85)/'proof #100%.db'
    extended='\\\\?\\'+str(path.resolve())
    __import__('os').makedirs(str(Path(extended).parent))
    with sqlite3.connect(extended) as db:
        db.execute('CREATE TABLE proof(value TEXT)');db.execute("INSERT INTO proof VALUES ('long')")
    assert len(str(path))>260
    with partial._ro(extended) as db:
        assert db.execute('SELECT value FROM proof').fetchall()==[('long',)]
        with pytest.raises(sqlite3.OperationalError,match='readonly'):db.execute('DROP TABLE proof')

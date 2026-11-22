"""Explicit eight-plus-missing peer completion; never a transport retry waiver.

prepare_plan/project_completion_request/completion_call are offline/pure. A receipt
requires a real successful, separately budgeted Narada completion before apply.
The original dispatch INCOMPLETE, raw and reservation never change. Apply records
the original HARD_FAILED logical row, marks only its logical cache as composite,
and adopts exactly one council stage. Every composite cache/future clearance is
reverified against the full receipt. No timeout authorization is used.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote

from src.orchestration.research_council import _check_answer, _json, VOICES, SOURCE_FIRST_SELECTION


def digest(value):
    """Return the existing provider-compatible canonical JSON SHA256."""
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _bytes(path):
    """Read exact local bytes; filesystem errors stop, never become guessed data."""
    return Path(path).read_bytes()


def _require(value,message):
    """Fail closed on an absent exact proof; no I/O or recovery on failure."""
    if not value:raise ValueError(message)


def _readonly_uri(path):
    """Encode an absolute SQLite path with no URI authority and strict mode=ro.

    Input: resolved absolute local/UNC path, including extended Windows paths.
    Return: file URI; native Windows prefixes/backslashes are percent-encoded
    intact, preserving long-path support without treating the prefix as a host.
    No I/O or network probes. Literal URI controls stay filename characters;
    unsupported relative paths raise ValueError through Path.as_uri.
    """
    value=str(path)
    if value.startswith('\\\\'):
        uri='file:'+quote(value,safe=':')
    elif re.match(r'^[A-Za-z]:[\\/]',value):
        uri='file:///'+quote(value.replace('\\','/'),safe='/:')
    else:uri=Path(value).as_uri()
    return uri+'?mode=ro'


def _ro(path):
    """Open an existing local/extended Windows SQLite path strictly read-only.

    Resolves the path before URI conversion; SQLite errors propagate without
    fallback, creation or write access. Debug invalid paths via _readonly_uri.
    """
    return sqlite3.connect(_readonly_uri(Path(path).resolve()),uri=True)


def _call_row(work,slot):
    """Return an actual boundary row with names; missing slots fail closed."""
    with _ro(Path(work)/'boundary.db') as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT * FROM calls WHERE slot=?',(slot,)).fetchone()
    _require(row is not None,'Saved call missing');return dict(row)


def _audit(work,raw_sha,status):
    """Find one actual role/model/truncation record; never manufacture token usage."""
    with _ro(Path(work)/'dispatch.db') as db:
        rows=[{'call_id':k,'record':json.loads(v)} for k,v in db.execute('SELECT call_id,record_json FROM council_dispatch_audit')]
    matches=[r for r in rows if r['record'].get('response_sha256')==raw_sha and r['record'].get('status')==status
             and r['record'].get('role')=='narada_specialist' and r['record'].get('provider')=='google'
             and r['record'].get('model_id')=='gemini-3.8-flash']
    _require(len(matches)==1,'Unique actual Gemini audit required');return matches[0]


def parse_prefix(raw,request):
    """Parse only complete JSON review objects in an attested truncated prefix.

    Return rows plus exact raw character spans and discarded-tail hash. Never
    close a partial object, infer a verdict or normalize an original judgment.
    """
    text=raw.decode('utf-8');match=re.match(r'\s*(?:```json\s*)?\{\s*"reviews"\s*:\s*\[\s*',text)
    _require(match is not None,'Exact reviews-array prefix required')
    def pairs(items):
        """Reject duplicate keys in any complete retained JSON object."""
        result={}
        for k,v in items:
            _require(k not in result,'Duplicate review JSON key');result[k]=v
        return result
    decoder=json.JSONDecoder(object_pairs_hook=pairs);position=match.end();rows=[];spans=[]
    while position<len(text):
        start=position
        _require(text[position:position+1]=='{','Expected review object, not trailing instructions')
        try:row,end=decoder.raw_decode(text,position)
        except json.JSONDecodeError:break
        _require(isinstance(row,dict),'Review object required')
        rows.append(row);spans.append({'start':start,'end':end,'utf8_sha256':hashlib.sha256(text[start:end].encode()).hexdigest()})
        position=end
        while position<len(text) and text[position].isspace():position+=1
        if position==len(text):break
        _require(text[position]==',','Expected incomplete next review after complete prefix')
        position+=1
        while position<len(text) and text[position].isspace():position+=1
    numbers=request['entry_numbers'];retained=[r.get('number') for r in rows]
    _require(rows and len(rows)<len(numbers) and retained==numbers[:len(rows)],'Strict nonempty ordered partial coverage required')
    sub={**request,'entry_numbers':retained,'proposal':{'proposals':[p for p in request['proposal']['proposals'] if p['number'] in retained]}}
    _check_answer('peer_review','narada',{'reviews':rows},sub)
    return {'rows':rows,'spans':spans,'discarded_tail_sha256':hashlib.sha256(text[position:].encode()).hexdigest(),'prefix_end':position}


def model_call(request):
    """Render the unchanged selection model view exactly, without an adapter/key."""
    from scripts import run_source_first_selection as s
    view=s.writing_view(request)
    view['literal_formula_exclusions']=view.pop('forbidden_originals')
    histories=[b.pop('selection_history') for b in view['briefs'] if 'selection_history' in b]
    _require(len(histories)==1,'Frozen batch history required')
    view['prior_accepted_decisions']=[h for h in histories[0] if h['status']=='ACCEPTED_FOR_CASE_ASSIGNMENT']
    view['held_selection_decisions']=[h for h in histories[0] if h['status']=='HOLD_PEER_REVIEW']
    view['role_focus']=s.ROLE_FOCUS['narada']
    return {'voice':'narada','stage':f"batch/{request['batch_id']}/peer_review",
            'system':s.SELECTION_SYSTEM+'\nROLE FOCUS: '+s.ROLE_FOCUS['narada'],
            'payload':{'instruction':s.selection_contract('peer_review',request),'input':view},
            'max_output_tokens':max(4096,len(request['entry_numbers'])*900)}


def prepare_plan(provider_work,council_db,source_input,forbidden_originals,failed_slot,*,
                 expected_request_sha256,expected_raw_sha256,expected_source_sha256):
    """Read/validate one actual truncated Narada peer stage and all cached siblings.

    Returns a frozen JSON plan. It authorizes no call or adoption. Only an actual
    INCOMPLETE max-tokens record with a matching failed logical row is eligible.
    """
    provider_work=Path(provider_work).resolve();council_db=Path(council_db).resolve();source_input=Path(source_input).resolve()
    row=_call_row(provider_work,failed_slot)
    _require(row['status']=='HARD_FAILED' and row['request_sha256']==expected_request_sha256
             and row['source_sha256']==expected_source_sha256 and row['raw_sha256']==expected_raw_sha256,'Exact original HARD_FAILED binding required')
    raw=_bytes(provider_work/'raw'/(failed_slot+'.txt'))
    _require(hashlib.sha256(raw).hexdigest()==expected_raw_sha256,'Original raw hash drift')
    audit=_audit(provider_work,expected_raw_sha256,'INCOMPLETE')
    _require('max_tokens' in str(audit['record'].get('finish_reason','')).lower(),'Only actual max-token truncation eligible')
    supplied=json.loads(_bytes(source_input).decode('utf-8-sig'))
    numbers=[b['number'] for b in supplied['briefs']]
    batch_id='selection-'+'-'.join(map(str,numbers))
    with _ro(council_db) as db:
        stages=db.execute('SELECT stage,speaker,request_hash,response_json FROM research_stages WHERE number=0').fetchall()
        attempts=db.execute("SELECT request_hash,state,error FROM research_attempts WHERE number=0 AND stage='peer_review' AND speaker='narada'").fetchall()
    _require(len(stages)==15 and {(a,b) for a,b,_,_ in stages}=={(st,v) for st in ('position','challenge','reply') for v in VOICES}|{('proposal','sutrakar'),('peer_review','shandilya'),('peer_review','researcher')},'Exactly fifteen cached completed sibling stages required')
    saved={(a,b):json.loads(v) for a,b,_,v in stages}
    base={'number':0,'brief':{'batch_id':batch_id},'sources':supplied['source_packets'],'scope':'batch','batch_id':batch_id,
          'briefs':supplied['briefs'],'entry_numbers':numbers,'sources_by_entry':supplied['source_packets'],
          'prior_formulas':supplied['prior_formulas'],'forbidden_originals':forbidden_originals,'used_case_ids':[],
          'source_first_selection':SOURCE_FIRST_SELECTION}
    request={**base,'discussion':{st:{v:saved[(st,v)] for v in VOICES} for st in ('position','challenge','reply')},
             'proposal':saved[('proposal','sutrakar')],'stage':'peer_review','speaker':'narada'}
    core_hash=hashlib.sha256(_json(request).encode()).hexdigest()
    _require(attempts and all(h==core_hash for h,_,_ in attempts) and attempts[-1][1]=='HARD_FAILED','Original council request/terminal attempt mismatch')
    call=model_call(request)
    with _ro(provider_work/'boundary.db') as db:config=db.execute('SELECT digest FROM config').fetchone()[0]
    calculated=digest({**call,'config':config,'sources':expected_source_sha256})
    _require(calculated==expected_request_sha256 and digest(['narada',call['stage']])==failed_slot,'Exact original paid model request mismatch')
    prefix=parse_prefix(raw,request)
    return {'kind':'PARTIAL_STAGE_COMPLETION_PLAN','provider_work':str(provider_work),'council_db':str(council_db),
            'source_input':{'path':str(source_input),'sha256':hashlib.sha256(_bytes(source_input)).hexdigest()},
            'failed_slot':failed_slot,'original_failed_row':row,'original_dispatch':audit,'original_core_request':request,
            'core_request_sha256':core_hash,'original_model_call':call,'prefix':prefix,
            'missing_numbers':numbers[len(prefix['rows']):],
            'cached_siblings':[{'stage':a,'speaker':b,'request_hash':h,'response_sha256':hashlib.sha256(v.encode()).hexdigest()} for a,b,h,v in sorted(stages)]}


def project_completion_request(plan):
    """Project ONLY missing entries and matching complete source/peer context."""
    request=deepcopy(plan['original_core_request']);numbers=plan['missing_numbers'];keys=set(map(str,numbers))
    history=next((deepcopy(b['selection_history']) for b in request['briefs'] if 'selection_history' in b),[])
    request['entry_numbers']=numbers;request['briefs']=[b for b in request['briefs'] if b['number'] in numbers]
    for b in request['briefs']:b.pop('selection_history',None)
    request['briefs'][0]['selection_history']=history
    request['sources']={k:v for k,v in request['sources'].items() if k in keys};request['sources_by_entry']=deepcopy(request['sources'])
    request['proposal']['proposals']=[p for p in request['proposal']['proposals'] if p['number'] in numbers]
    for stage,voices in request['discussion'].items():
        field={'position':'positions','challenge':'challenges','reply':'answers'}[stage]
        for answer in voices.values():
            if stage=='position':answer[field]={k:v for k,v in answer[field].items() if k in keys}
            else:
                for peer in answer[field]:answer[field][peer]={k:v for k,v in answer[field][peer].items() if k in keys}
    request['batch_id']='partial-'+plan['failed_slot'];request['brief']={'batch_id':request['batch_id']}
    return request


def completion_call(plan,stage='missing-peer-review'):
    """Return the exact separate one-Gemini-call specification; no API invocation."""
    call=model_call(project_completion_request(plan));call['stage']=stage;call['max_output_tokens']=16384
    call['generation_options']={'thinking_level':'MEDIUM'}
    call['payload']['instruction']+=' Complete ONLY these missing review numbers; do not re-review any retained prefix entry.'
    return call


def _verify_original(plan):
    """Recheck immutable originals/siblings while allowing only explicit logical adoption."""
    row=_call_row(plan['provider_work'],plan['failed_slot']);old=plan['original_failed_row']
    _require(all(row[k]==old[k] for k in ('slot','request_sha256','source_sha256','raw_sha256')),'Original identity drift')
    _require(row==old or (row['status']=='SUCCESS' and row['error_type']=='COMPOSITE_RECOVERED'),'Unrecognized original logical state')
    request=plan['original_core_request']
    _require(hashlib.sha256(_json(request).encode()).hexdigest()==plan['core_request_sha256'],'Original proposal/core request altered')
    with _ro(plan['council_db']) as db:
        attempts=db.execute("SELECT request_hash,state FROM research_attempts WHERE number=0 AND stage='peer_review' AND speaker='narada'").fetchall()
    _require(attempts and all(h==plan['core_request_sha256'] for h,_ in attempts) and attempts[-1][1]=='HARD_FAILED','Original failed council lineage altered')
    with _ro(Path(plan['provider_work'])/'boundary.db') as db:config=db.execute('SELECT digest FROM config').fetchone()[0]
    _require(model_call(request)==plan['original_model_call'] and digest({**plan['original_model_call'],'config':config,'sources':old['source_sha256']})==old['request_sha256'],'Original paid request/proposal binding changed')
    raw=_bytes(Path(plan['provider_work'])/'raw'/(plan['failed_slot']+'.txt'))
    _require(hashlib.sha256(raw).hexdigest()==old['raw_sha256'],'Original truncated raw changed')
    _require(_audit(plan['provider_work'],old['raw_sha256'],'INCOMPLETE')==plan['original_dispatch'],'Original dispatch/reservation changed')
    _require(hashlib.sha256(_bytes(plan['source_input']['path'])).hexdigest()==plan['source_input']['sha256'],'Original input changed')
    _require(parse_prefix(raw,plan['original_core_request'])==plan['prefix'],'Original prefix altered')
    with _ro(plan['council_db']) as db:
        for stage in plan['cached_siblings']:
            found=db.execute('SELECT request_hash,response_json FROM research_stages WHERE number=0 AND stage=? AND speaker=?',(stage['stage'],stage['speaker'])).fetchone()
            _require(found and found[0]==stage['request_hash'] and hashlib.sha256(found[1].encode()).hexdigest()==stage['response_sha256'],'Cached sibling changed')


def finalize_receipt(plan,completion_provider_work,completion_stage='missing-peer-review',completion_budget=0.25):
    """Bind actual missing-row SDK success and ten-row validation into a receipt.

    No synthetic model result, failed replacement or unrelated source/request can
    clear the original failure. Original reservation stays in its original ledger.
    """
    _verify_original(plan);work=Path(completion_provider_work).resolve();call=completion_call(plan,completion_stage)
    _require(type(completion_budget) in (int,float) and 0 < completion_budget <= .25,'Explicit completion allowance must be <=0.25 USD')
    from scripts.run_research_book import RATES
    expected_budget_hash=hashlib.sha256(json.dumps({'rates':RATES,'max_usd':completion_budget,'max_calls':1,'max_elapsed_seconds':172800,'role_timeouts':{}},sort_keys=True).encode()).hexdigest()
    with _ro(work/'dispatch.db') as budget_db:
        _require(budget_db.execute('SELECT config_sha256 FROM council_run_config').fetchall()==[(expected_budget_hash,)],'Completion persisted cap/call configuration mismatch')
    slot=digest(['narada',completion_stage]);row=_call_row(work,slot)
    _require(row['status']=='SUCCESS' and row['source_sha256']==digest({'partial_plan':digest(plan)}),'Completion success/plan binding required')
    with _ro(work/'boundary.db') as db:
        config=db.execute('SELECT digest FROM config').fetchone()[0]
        _require(db.execute('SELECT count(*) FROM calls').fetchone()[0]==1,'Exactly one completion call allowed')
    _require(row['request_sha256']==digest({**call,'config':config,'sources':row['source_sha256']}),'Completion actual request mismatch')
    raw=_bytes(work/'raw'/(slot+'.txt'));_require(hashlib.sha256(raw).hexdigest()==row['raw_sha256'],'Completion raw changed')
    from src.orchestration.source_first_provider import parse_saved_response
    answer=json.loads(row['result_json'])
    _require(parse_saved_response(work,slot,raw)==answer,'Completion raw/result mismatch')
    _require(digest(answer)==row['result_sha256'],'Completion parsed hash drift')
    _check_answer('peer_review','narada',answer,project_completion_request(plan))
    audit=_audit(work,row['raw_sha256'],'SUCCESS')
    _require(isinstance(audit['record'].get('raw_usage'),dict),'Completion raw SDK usage counters must be durably recorded')
    _require(audit['record'].get('max_output_tokens')==16384,'Completion headroom audit mismatch')
    merged={'reviews':deepcopy(plan['prefix']['rows'])+deepcopy(answer['reviews'])}
    _check_answer('peer_review','narada',merged,plan['original_core_request'])
    return {'kind':'PARTIAL_STAGE_COMPLETION','plan':plan,'completion':{'provider_work':str(work),'stage':completion_stage,'budget':completion_budget,'row':row,'dispatch':audit},
            'merged':merged,'merged_sha256':digest(merged),'original_api_returned_full_stage':False,
            'original_failed_reservation_retained':True,'separate_completion_budget_max_usd':0.25}


def verify_receipt(path,expected_sha256):
    """Verify complete proof on every replay/clearance; return the composite review."""
    raw=_bytes(path);_require(hashlib.sha256(raw).hexdigest()==expected_sha256,'Composite receipt bytes changed')
    receipt=json.loads(raw.decode('utf-8'));_require(receipt.get('kind')=='PARTIAL_STAGE_COMPLETION','Explicit completion kind required')
    rebuilt=finalize_receipt(receipt['plan'],receipt['completion']['provider_work'],receipt['completion']['stage'],receipt['completion']['budget'])
    _require(rebuilt==receipt,'Composite receipt proof/content drift')
    row=_call_row(receipt['plan']['provider_work'],receipt['plan']['failed_slot'])
    if row['error_type']=='COMPOSITE_RECOVERED':
        answer={**receipt['merged'],'partial_stage_completion':{'path':str(Path(path).resolve()),'sha256':expected_sha256}}
        _require(row['result_json']==json.dumps(answer,ensure_ascii=False,sort_keys=True,separators=(',',':'))
                 and row['result_sha256']==digest(answer),'Composite logical result drift')
    return receipt,deepcopy(receipt['merged'])


def apply_receipt(path):
    """Explicit offline adoption after real completion; preserve dispatch/raw/failed attempt.

    Two attached SQLite databases share a transaction. New logical SUCCESS always
    carries COMPOSITE_RECOVERED and a mandatory full-verification receipt pointer.
    """
    path=Path(path).resolve();sha=hashlib.sha256(_bytes(path)).hexdigest();receipt,merged=verify_receipt(path,sha)
    plan=receipt['plan'];pointer={'path':str(path),'sha256':sha}
    answer={**merged,'partial_stage_completion':pointer}
    with sqlite3.connect(Path(plan['provider_work'])/'boundary.db') as db:
        db.execute('ATTACH DATABASE ? AS council',(plan['council_db'],));db.execute('BEGIN IMMEDIATE')
        _verify_original(plan)
        db.execute('CREATE TABLE IF NOT EXISTS partial_stage_completions(slot TEXT PRIMARY KEY, receipt_path TEXT NOT NULL,receipt_sha256 TEXT NOT NULL)')
        old=db.execute('SELECT receipt_path,receipt_sha256 FROM partial_stage_completions WHERE slot=?',(plan['failed_slot'],)).fetchone()
        _require(old is None or old==(str(path),sha),'Different composite authority already exists')
        db.execute('INSERT OR IGNORE INTO partial_stage_completions VALUES (?,?,?)',(plan['failed_slot'],str(path),sha))
        db.execute("UPDATE calls SET status='SUCCESS',result_json=?,result_sha256=?,error_type='COMPOSITE_RECOVERED' WHERE slot=?",(json.dumps(answer,ensure_ascii=False,sort_keys=True,separators=(',',':')),digest(answer),plan['failed_slot']))
        existing=db.execute("SELECT request_hash,response_json FROM council.research_stages WHERE number=0 AND stage='peer_review' AND speaker='narada'").fetchone()
        expected=(plan['core_request_sha256'],_json(answer))
        _require(existing is None or existing==expected,'Council stage adoption conflict')
        db.execute("INSERT OR IGNORE INTO council.research_stages VALUES (0,'peer_review','narada',?,?)",expected)
    return {'status':'COMPOSITE_RECOVERED','receipt':pointer,'rows':[r['number'] for r in merged['reviews']]}


def verify_authorities(provider_work):
    """Revalidate every composite before cached response or future-call clearance."""
    with _ro(Path(provider_work)/'boundary.db') as db:
        markers={r[0] for r in db.execute("SELECT slot FROM calls WHERE error_type='COMPOSITE_RECOVERED'")}
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='partial_stage_completions'").fetchone()
        _require(exists or not markers,'Composite marker has no mandatory authority table')
        rows=db.execute('SELECT slot,receipt_path,receipt_sha256 FROM partial_stage_completions').fetchall() if exists else []
        successes=db.execute("SELECT raw_sha256,error_type FROM calls WHERE status='SUCCESS'").fetchall()
    _require({r[0] for r in rows}==markers,'Composite marker/authority coverage mismatch')
    with _ro(Path(provider_work)/'dispatch.db') as db:
        incomplete={json.loads(raw).get('response_sha256') for raw, in db.execute("SELECT record_json FROM council_dispatch_audit WHERE status='INCOMPLETE'")}
    _require(all(raw not in incomplete or marker=='COMPOSITE_RECOVERED' for raw,marker in successes),
             'Incomplete API result cannot masquerade as ordinary logical success')
    for slot,path,sha in rows:
        receipt,merged=verify_receipt(path,sha);answer={**merged,'partial_stage_completion':{'path':path,'sha256':sha}}
        plan=receipt['plan'];row=_call_row(provider_work,slot);old=plan['original_failed_row']
        _require(Path(plan['provider_work']).resolve()==Path(provider_work).resolve()
                 and plan['failed_slot']==slot
                 and all(row[k]==old[k] for k in ('slot','request_sha256','source_sha256','raw_sha256')),
                 'Composite authority belongs to a different root/slot/original call')
        _require(row['status']=='SUCCESS' and row['error_type']=='COMPOSITE_RECOVERED' and row['result_json']==json.dumps(answer,ensure_ascii=False,sort_keys=True,separators=(',',':')) and row['result_sha256']==digest(answer),'Composite logical cache changed')
